import time
import random
import queue

# =============================================================================
# 1. LA DOUBLURE (MOCK) - Pour remplacer GNU Radio
# =============================================================================
class MockPMT:
    """Imite le comportement de la librairie PMT de GNU Radio"""
    def intern(self, s): return s
    def to_pmt(self, x): return x
    def from_bool(self, x): return x
    def to_python(self, x): return x
    def cons(self, a, b): return (a, b) # Une paire devient un tuple
    def cdr(self, x): return x[1] if isinstance(x, tuple) else x
    def is_pair(self, x): return isinstance(x, tuple)
    def PMT_NIL(self): return None

class MockGR:
    """Imite le bloc de base GNU Radio"""
    class basic_block:
        def __init__(self, name="", in_sig=None, out_sig=None):
            self.name = name
            # Simulation des ports de messages (dictionnaire de queues)
            self.msg_ports_out = {} 
            
        def message_port_register_in(self, port_name):
            pass # On ne fait rien de spécial ici pour la simu
            
        def message_port_register_out(self, port_name):
            self.msg_ports_out[port_name] = [] # Liste des abonnés
            
        def set_msg_handler(self, port, handler):
            # On stocke le handler pour pouvoir l'appeler manuellement
            setattr(self, f"_handler_{port}", handler)
            
        def message_port_pub(self, port, msg):
            """Quand le bloc publie un message, on l'affiche et on le transmet"""
            print(f"   [{self.name}] >> OUTPUT sur '{port}': {msg}")
            # Dans une vraie simu, on enverrait ça au bloc connecté
            # Ici, géré par le 'Simulator' plus bas
            if hasattr(self, 'simulator_callback'):
                self.simulator_callback(self.name, port, msg)

        
# On instancie les faux modules
pmt = MockPMT()
gr = MockGR()

class aloha_mac_block(gr.basic_block):
    def __init__(self, name="ALOHA_NODE", mac_addr=1, ack_timeout=2.0, max_retries=2):
        gr.basic_block.__init__(self, name=name)
        
        self.mac_addr = mac_addr
        self.ack_timeout = ack_timeout
        self.max_retries = max_retries
        
        self.state = "IDLE"
        self.current_payload = None
        self.retries = 0
        
        self.tx_queue = queue.Queue()
        self.timer_start = 0
        self.backoff_duration = 0
        
        # Ports
        self.message_port_register_in(pmt.intern("app_in"))
        self.message_port_register_in(pmt.intern("phy_in"))
        self.message_port_register_out(pmt.intern("phy_out"))
        self.message_port_register_out(pmt.intern("app_out"))
        
        # Handlers
        self.set_msg_handler(pmt.intern("app_in"), self.handle_msg_in)
        self.set_msg_handler(pmt.intern("phy_in"), self.handle_phy_in)

    def handle_msg_in(self, msg):
        """Reçoit une demande d'envoi de l'application"""
        print(f"[{self.name}] Reçu de APP: {msg}")
        self.tx_queue.put(msg)
        if self.state == "IDLE":
            self.process_next_packet()

    def process_next_packet(self):
        if not self.tx_queue.empty():
            self.current_payload = self.tx_queue.get()
            self.retries = 0
            self.tx_frame()

    def tx_frame(self):
        """Envoi Physique"""
        print(f"[{self.name}] ** TX ** Envoi trame (Essai {self.retries + 1})")
        # Structure simple simulée : (src, dst, type, data)
        # Type: 0 = Data, 1 = ACK
        frame = (self.mac_addr, 2, 0, self.current_payload) 
        
        self.message_port_pub(pmt.intern("phy_out"), frame)
        
        self.state = "WAIT_ACK"
        self.timer_start = time.time()

    def handle_phy_in(self, msg):
        """Réception Physique"""
        # msg est un tuple (src, dst, type, payload)
        src, dst, mtype, data = msg
        
        if dst != self.mac_addr: return # Pas pour moi

        if mtype == 1: # C'est un ACK
            if self.state == "WAIT_ACK":
                print(f"[{self.name}] ** RX ** ACK reçu de {src} ! Succès.")
                self.state = "IDLE"
                self.process_next_packet()
        
        elif mtype == 0: # C'est des DATA
            print(f"[{self.name}] ** RX ** Données reçues : {data}")
            # On renvoie un ACK
            ack_frame = (self.mac_addr, src, 1, "ACK")
            print(f"[{self.name}] Envoi de l'ACK vers {src}")
            self.message_port_pub(pmt.intern("phy_out"), ack_frame)

    def tick(self):
        """Fonction appelée régulièrement pour simuler le temps (Clock)"""
        now = time.time()
        
        if self.state == "WAIT_ACK":
            if (now - self.timer_start) > self.ack_timeout:
                print(f"[{self.name}] !! TIMEOUT !! Pas d'ACK reçu.")
                self.handle_tx_failure()

        elif self.state == "BACKOFF":
            if (now - self.timer_start) > self.backoff_duration:
                print(f"[{self.name}] Fin du Backoff. Retransmission...")
                self.tx_frame()

    def handle_tx_failure(self):
        self.retries += 1
        if self.retries <= self.max_retries:
            self.backoff_duration = random.uniform(0.5, 1.5)
            print(f"[{self.name}] Passage en BACKOFF pour {self.backoff_duration:.2f}s")
            self.state = "BACKOFF"
            self.timer_start = time.time()
        else:
            print(f"[{self.name}] ÉCHEC DÉFINITIF. Abandon du paquet.")
            self.state = "IDLE"
            self.process_next_packet()

# =============================================================================
# 3. LE SIMULATEUR (Le chef d'orchestre)
# =============================================================================
if __name__ == "__main__":
    print("--- Démarrage de la simulation ALOHA ---")
    
    # 1. Création des nœuds
    node_A = aloha_mac_block(name="Node_A", mac_addr=1)
    node_Base = aloha_mac_block(name="Base_Station", mac_addr=2)

    # 2. Câblage virtuel (Callback)
    # Quand A émet sur PHY_OUT, on l'injecte dans PHY_IN de Base (et vice versa)
    def wire_transfer(sender_name, port, msg):
        if port == "phy_out":
            # 30% de chance de perdre le paquet (Collision simulée)
            if random.random() < 0.3:
                print(f"   [AIR] X COLLISION X - Message perdu !")
                return 

            if sender_name == "Node_A":
                node_Base._handler_phy_in(msg)
            # ...
    node_A.simulator_callback = wire_transfer
    node_Base.simulator_callback = wire_transfer

    # 3. Scénario de Test
    # On injecte un message dans Node A
    print("\n--- Scénario 1: Transmission réussie ---")
    node_A._handler_app_in("DATA: Température 22°C")

    # 4. Boucle de temps (Simulation Loop)
    # On fait tourner la boucle pendant 5 secondes
    start_sim = time.time()
    while (time.time() - start_sim) < 10:
        node_A.tick()
        node_Base.tick()
        time.sleep(0.1)
        
    print("\n--- Fin de simulation ---")