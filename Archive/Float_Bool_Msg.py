import pmt
from gnuradio import gr
import numpy as np

class float_to_bool_msg(gr.basic_block):
    """
    Convertit un flux float32 (0 ou 1) en messages booléens (False ou True).
    """
    def __init__(self):
        gr.basic_block.__init__(
            self,
            name="float_to_bool_msg",
            in_sig=[np.float32],  # un canal d'entrée float32
            out_sig=[]                  # pas de flux de sortie
        )
        
        # On déclare un port de sortie de message
        self.message_port_register_out(pmt.intern("state_out"))

    def general_work(self, input_items, output_items):
        in0 = input_items[0]
        n = len(in0)
        
        # Pour chaque échantillon, on envoie un message
        for val in in0:
            if val >= 0.5:  # ou > 0.0 selon votre logique
                msg = pmt.from_bool(False)
            else:
                msg = pmt.from_bool(True)
            
            # Publier le message
            self.message_port_pub(pmt.intern("state_out"), msg)
        
        # Consommer tous les échantillons
        self.consume(0, n)
        
        return 0