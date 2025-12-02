#!/usr/bin/env python3
import time
import random
import pmt
from gnuradio import gr
import numpy as np
import json

class app_simulator(gr.basic_block):
    """
    Simulateur de la couche application qui envoie des données toutes les 30 secondes.
    Les données sont envoyées au format attendu par le bloc CSMA/CA.
    """
    def __init__(self, 
                 interval=30.0,  # Intervalle entre les envois en secondes
                 dst_mac=b'\xFF\xFF\xFF\xFF\xFF\xFF',  # Broadcast par défaut
                 min_size=10,    # Taille minimum des données en octets
                 max_size=100):  # Taille maximum des données en octets
        gr.basic_block.__init__(
            self,
            name="app_simulator",
            in_sig=None,
            out_sig=None
        )
        
        self.interval = interval
        self.dst_mac = dst_mac
        self.min_size = min_size
        self.max_size = max_size
        
        # Pour le timing
        self.last_tx = time.time()

        # Pour la clock de work
        self.message_port_register_in(pmt.intern("clock"))
        self.set_msg_handler(pmt.intern("clock"), self.general_work)
        
        # Port de sortie vers la couche MAC
        self.message_port_register_out(pmt.intern("app_out"))
        
        # Port optionnel pour recevoir les acquittements
        self.message_port_register_in(pmt.intern("app_in"))
        self.set_msg_handler(pmt.intern("app_in"), self.handle_mac_feedback)
    
    def handle_mac_feedback(self, msg_pmt):
        """
        Traite les retours de la couche MAC (succès/échec des transmissions)
        """
        if pmt.is_pair(msg_pmt):
            key = pmt.symbol_to_string(pmt.car(msg_pmt))
            if key == "tx_success":
                print("[APP] Transmission réussie")
            elif key == "tx_failed":
                print("[APP] Échec de la transmission")
            elif key == "rx_frame":
                # Données reçues d'un autre nœud
                data_dict = pmt.to_python(pmt.cdr(msg_pmt))
                print(f"[APP] Données reçues de {data_dict['src_mac']}: {data_dict['data']}")
    
    def generate_random_data(self):
        """
        Génère des données aléatoires de taille variable
        """
        size = random.randint(self.min_size, self.max_size)
        # Simuler des données de capteur (température, humidité, etc.)
        temp = round(random.uniform(15, 30), 2)
        humidity = round(random.uniform(30, 80), 2)
        data = f"T{temp},H{humidity}" #.encode('utf-8')
        return data
    
    def general_work(self, clk):
        """
        Méthode appelée régulièrement par le scheduler de GNU Radio
        """
        now = time.time()
        
        # Vérifier si c'est le moment d'envoyer
        if (now - self.last_tx) >= self.interval:
            # Générer des données
            data = self.generate_random_data()
            
            # Créer le message pour la couche MAC
            msg_dict = {
                "dst_mac": self.dst_mac,
                "priority": random.randint(0, 1),  # Priorité aléatoire
                "data": data
            }
            msg_str = json.dumps(msg_dict)
            
            # Convertir en PMT et envoyer
            try:
                self.message_port_pub(
                    pmt.intern("app_out"),
                    pmt.cons(pmt.PMT_NIL, pmt.to_pmt(msg_str))
                )
                #print(f"[APP] Envoi de données: {data}")
            except Exception as e:
                print(f"[APP] Erreur lors de l'envoi: {e}")
            
            self.last_tx = now
        
        return 0

print("fichier simu présent")