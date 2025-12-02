import struct
import time
import random
import pmt
import json
from queue import Queue
from gnuradio import gr

def build_frame(src_mac, dst_mac, priority, data):
    """
    Construit la trame MAC :
      - src_mac: 6 octets
      - dst_mac: 6 octets
      - priority: 1 octet (0 ou 1)
      - length: 2 octets (taille des données)
      - data: N octets
    """
    # s = string (bytes), B = unsigned char, H = unsigned short
    length = len(data)
    fmt_header = "!IIBH"  # ! = réseau (big-endian)
    header = struct.pack(fmt_header, src_mac, dst_mac, priority, length)
    print(header)
    return header + data

def parse_frame(frame_bytes):
    """
    Décode une trame MAC.
    Retourne (src_mac, dst_mac, priority, data).
    """
    fmt_header = "!IIBH"
    header_size = struct.calcsize(fmt_header)
    header = frame_bytes[:header_size]
    data = frame_bytes[header_size:]

    src_mac, dst_mac, priority, length = struct.unpack(fmt_header, header)
    payload = data[:length]
    return src_mac, dst_mac, priority, payload

class csma_ca_mac_block(gr.basic_block):
    """
    Bloc CSMA/CA avec backoff exponentiel et priorités pour GNU Radio.
    """
    def __init__(self, 
                 mac_addr=1,   # MAC de ce noeud
                 cw_min_low=8,
                 cw_min_high=4,
                 cw_max=64,
                 ack_timeout=0.05,  # en secondes
                 max_retries=3):
        gr.basic_block.__init__(
            self,
            name="csma_ca_mac_block",
            in_sig=None,
            out_sig=None
        )
        
        # Adresse MAC de ce noeud
        self.mac_addr = mac_addr
        
        # Paramètres
        self.cw_min_low = cw_min_low
        self.cw_min_high = cw_min_high
        self.cw_max = cw_max
        self.ack_timeout = ack_timeout
        self.max_retries = max_retries
        
        # État interne
        self.state = "IDLE"
        self.current_frame = None
        self.current_priority = 0
        self.cw = cw_min_low
        self.retries = 0
        
        # File d'attente des paquets à transmettre
        self.tx_queue = Queue() 
        
        # Canal occupé ?
        self.channel_busy = False
        
        # Timer pour le backoff
        self.backoff_remaining = 0
        self.last_time = time.time()
        
        # Ports de messages
        self.message_port_register_in(pmt.intern("app_in"))
        self.message_port_register_in(pmt.intern("phy_in"))
        self.message_port_register_in(pmt.intern("cs_in"))  # Carrier Sense input
        self.message_port_register_out(pmt.intern("phy_out"))
        self.message_port_register_out(pmt.intern("app_out"))

        # Pour la clock de work
        self.message_port_register_in(pmt.intern("clock"))
        self.set_msg_handler(pmt.intern("clock"), self.general_work)
        
        self.set_msg_handler(pmt.intern("app_in"), self.handle_msg_in)
        self.set_msg_handler(pmt.intern("phy_in"), self.handle_phy_in)
        self.set_msg_handler(pmt.intern("cs_in"), self.handle_cs_in)

    def handle_msg_in(self, msg_pmt):
        """
        Handler pour une nouvelle trame à émettre depuis la couche application
        """
        try:
            # Extraire les données du message PMT
            if pmt.is_pair(msg_pmt):
                msg_str = pmt.to_python(pmt.cdr(msg_pmt))
                msg_dict = json.loads(msg_str)
                if isinstance(msg_dict, dict):
                    dst_mac = msg_dict.get("dst_mac")
                    priority = msg_dict.get("priority")
                    data = msg_dict.get("data")
                    
                    # Construire la trame MAC
                    #frame = build_frame(self.mac_addr, dst_mac, priority, data)
                    
                    # Mettre en file d'attente
                    self.tx_queue.put((msg_str, priority))
                    
                    # Si on est IDLE, traiter immédiatement
                    if self.state == "IDLE":
                        self.process_next_packet()
        except Exception as e:
            print(f"Error in handle_msg_in: {e}")
    
    def handle_new_frame(self, frame, priority):
        """
        Démarre la procédure de transmission pour une nouvelle trame
        """
        if self.state == "IDLE":
            self.current_frame = frame
            self.current_priority = priority
            self.retries = 0
            # Définir la CW initiale selon la priorité
            if priority == 1:
                self.cw = self.cw_min_high
            else:
                self.cw = self.cw_min_low
            # Passer en BACKOFF
            self.state = "BACKOFF"
            self.start_backoff()
    
    def start_backoff(self):
        """
        Démarre la procédure de backoff de manière asynchrone
        """
        # Déterminer le backoff en slots
        slots = random.randint(0, self.cw - 1)
        self.backoff_remaining = slots * 0.001  # 1ms par slot
        self.last_time = time.time()
    
    def tx_frame(self):
        """
        Transmet une trame via le port PHY
        """
        try:
            # Créer un vecteur PMT pour la trame
            #blob = pmt.make_u8vector(len(self.current_frame), 0)
            #for i, b in enumerate(self.current_frame):
                #pmt.u8vector_set(blob, i, b)
            
            # Envoyer la trame
            self.message_port_pub(
                pmt.intern("phy_out"),
                pmt.cons(pmt.intern("frame"), pmt.to_pmt(self.current_frame))#pmt.cons(pmt.intern("frame"), blob)
            )
            
            # Passer en attente d'ACK
            self.state = "WAIT_ACK"
            self.wait_ack_start_time = time.time()
            
        except Exception as e:
            print(f"Error in tx_frame: {e}")
            self.state = "IDLE"
            self.process_next_packet()
    
    def handle_phy_in(self, msg_pmt):
        """
        Réception d'une trame depuis la PHY
        """
        try:
            if pmt.is_pair(msg_pmt):
                blob = pmt.cdr(msg_pmt)
                if pmt.is_u8vector(blob):
                    # Convertir le PMT en bytes
                    frame_bytes = bytes(pmt.u8vector_elements(blob))
                    
                    # Parser la trame
                    src_mac, dst_mac, priority, payload = parse_frame(frame_bytes)
                    
                    # Vérifier si c'est un ACK pour nous
                    if payload == b'ACK' and dst_mac == self.mac_addr:
                        self.handle_rx_ack(src_mac)
                    elif dst_mac == self.mac_addr or dst_mac == b'\xFF\xFF\xFF\xFF\xFF\xFF':
                        # Trame de données pour nous ou broadcast
                        # Remonter à la couche application
                        msg_dict = {
                            "src_mac": src_mac,
                            "priority": priority,
                            "data": payload
                        }
                        self.message_port_pub(
                            pmt.intern("app_out"),
                            pmt.cons(pmt.intern("rx_frame"), pmt.to_pmt(msg_dict))
                        )
        except Exception as e:
            print(f"Error in handle_phy_in: {e}")
    
    def handle_rx_ack(self, ack_src_mac):
        """
        Traitement quand on reçoit un ACK
        """
        if self.state == "WAIT_ACK":
            # Extract destination MAC from the current frame (bytes 6-12 in the frame)
            _, dst_mac, _, _ = parse_frame(self.current_frame)
            
            # Verify ACK came from the intended recipient
            if ack_src_mac == dst_mac:
                self.state = "IDLE"
                self.current_frame = None
                # Notifier le succès
                self.message_port_pub(
                    pmt.intern("app_out"),
                    pmt.cons(pmt.intern("tx_success"), pmt.PMT_NIL)
                )
            else:
                # If ACK came from wrong source, treat it as no ACK received
                print(f"Received ACK from unexpected source: {ack_src_mac}")
                self.retries += 1
                if self.retries < self.max_retries:
                    self.cw = min(self.cw * 2, self.cw_max)
                    self.state = "BACKOFF"
                    self.start_backoff()
                else:
                    self.state = "IDLE"
                    self.current_frame = None
                    # Notifier l'échec
                    self.message_port_pub(
                        pmt.intern("app_out"),
                        pmt.cons(pmt.intern("tx_failed"), pmt.PMT_NIL)
                    )
                    # Traiter le paquet suivant dans la file
                    self.process_next_packet()
    
    def handle_cs_in(self, msg_pmt):
        """
        Gestion du Carrier Sense
        """
        if pmt.is_bool(msg_pmt):
            self.channel_busy = pmt.to_bool(msg_pmt)
    
    def general_work(self, clk):
        """
        Méthode appelée régulièrement par le scheduler de GNU Radio
        """
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        
        if self.state == "BACKOFF":
            if not self.channel_busy:
                self.backoff_remaining -= dt
                if self.backoff_remaining <= 0:
                    self.state = "TX"
                    self.tx_frame()
        
        elif self.state == "WAIT_ACK":
            if (now - self.wait_ack_start_time) > self.ack_timeout:
                self.retries += 1
                if self.retries < self.max_retries:
                    self.cw = min(self.cw * 2, self.cw_max)
                    self.state = "BACKOFF"
                    self.start_backoff()
                else:
                    self.state = "IDLE"
                    self.current_frame = None
                    # Notifier l'échec
                    self.message_port_pub(
                        pmt.intern("app_out"),
                        pmt.cons(pmt.intern("tx_failed"), pmt.PMT_NIL)
                    )
                    # Traiter le paquet suivant dans la file
                    self.process_next_packet()
        
        return 0

    def process_next_packet(self):
        """
        Traite le prochain paquet dans la file d'attente
        """
        if not self.tx_queue.empty() and self.state == "IDLE":
            frame, priority = self.tx_queue.get()
            self.handle_new_frame(frame, priority)

    def stop(self):
        """
        Nettoie les ressources à l'arrêt du flowgraph.
        """
        return super().stop()

print("fichier présent")