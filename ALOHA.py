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


class aloha_mac_block(gr.basic_block):
    """
    Bloc ALOHA PUR avec ACK et Retransmissions.
    Principe : J'envoie -> J'attends ACK -> Si Timeout, j'attends Random -> Je réessaie.
    """
    def __init__(self, 
                 mac_addr=1, 
                 ack_timeout=0.1,   # Temps d'attente de l'ACK (ajuster selon la couche PHY)
                 max_retries=3,     # Nombre d'essais max
                 max_backoff=1.0):  # Temps max d'attente aléatoire après échec
        gr.basic_block.__init__(
            self,
            name="ALOHA MAC",
            in_sig=None,
            out_sig=None
        )
        
        self.mac_addr = mac_addr
        self.ack_timeout = ack_timeout
        self.max_retries = max_retries
        self.max_backoff = max_backoff
        
        # État interne
        self.state = "IDLE"
        self.current_frame = None
        self.retries = 0
        
        # File d'attente
        self.tx_queue = Queue() 
        
        # Timers
        self.timer_start = 0
        self.backoff_duration = 0
        
        # Ports (Note: Plus de cs_in)
        self.message_port_register_in(pmt.intern("app_in"))
        self.message_port_register_in(pmt.intern("phy_in"))
        self.message_port_register_out(pmt.intern("phy_out"))
        self.message_port_register_out(pmt.intern("app_out"))

        # Clock
        self.message_port_register_in(pmt.intern("clock"))
        self.set_msg_handler(pmt.intern("clock"), self.general_work)
        
        self.set_msg_handler(pmt.intern("app_in"), self.handle_msg_in)
        self.set_msg_handler(pmt.intern("phy_in"), self.handle_phy_in)

    def handle_msg_in(self, msg_pmt):
        """ Nouvelle donnée à envoyer """
        # ... (Extraction du JSON identique au script précédent) ...
        # Pour l'exemple simplifié :
        try:
            msg_str = pmt.to_python(pmt.cdr(msg_pmt))
            self.tx_queue.put(msg_str) # On stocke juste le message brut pour simplifier l'exemple
            
            if self.state == "IDLE":
                self.process_next_packet()
        except:
            pass

    def process_next_packet(self):
        """ Prépare l'envoi """
        if not self.tx_queue.empty():
            msg_str = self.tx_queue.get()
            # Construction fictive de la trame (à adapter avec build_frame)
            # self.current_frame = build_frame(...) 
            self.current_frame = bytes(msg_str, 'utf-8') # Simplification
            
            self.retries = 0
            self.tx_frame() # DANS ALOHA, ON TIRE DIRECTEMENT !

    def tx_frame(self):
        """ Envoi physique """
        # Envoi au PHY
        self.message_port_pub(pmt.intern("phy_out"), 
                              pmt.cons(pmt.intern("frame"), 
                              pmt.to_pmt(self.current_frame)))
        
        # On passe en attente d'ACK
        self.state = "WAIT_ACK"
        self.timer_start = time.time()

    def general_work(self, clk):
        """ Machine d'état gérée par l'horloge """
        now = time.time()
        
        if self.state == "WAIT_ACK":
            # Timeout : Pas d'ACK reçu à temps
            if (now - self.timer_start) > self.ack_timeout:
                self.handle_tx_failure()

        elif self.state == "BACKOFF":
            # On attend un temps aléatoire avant de réessayer
            if (now - self.timer_start) > self.backoff_duration:
                self.tx_frame() # On réessaie d'envoyer

    def handle_tx_failure(self):
        """ Gestion de l'échec (Collision probable) """
        self.retries += 1
        if self.retries < self.max_retries:
            # On calcule un temps d'attente aléatoire
            self.backoff_duration = random.uniform(0.1, self.max_backoff)
            self.timer_start = time.time()
            self.state = "BACKOFF"
            #print(f"Collision/Perte. Nouvel essai dans {self.backoff_duration:.2f}s")
        else:
            # Échec définitif
            self.state = "IDLE"
            self.message_port_pub(pmt.intern("app_out"), pmt.cons(pmt.intern("tx_failed"), pmt.PMT_NIL))
            self.process_next_packet()

    def handle_phy_in(self, msg_pmt):
        """ Réception (ACK ou Données) """
        # ... (Logique de parsing identique) ...
        # Si c'est un ACK pour moi :
        #    self.state = "IDLE"
        #    self.process_next_packet()
        pass