from gnuradio import gr
import pmt
import numpy as np
import json


class ichar_to_pmt(gr.sync_block):
    """
    Bloc GNU Radio pour transformer un flux d'entiers (int8) en un message PMT
    """

    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="Ichar to PMT",
            in_sig=[np.int8],
            out_sig=[],
        )
        self.message_port_register_out(pmt.intern("out"))
        self.data_buffer = bytearray()

    def work(self, input_items, output_items):
        in_data = input_items[0]

        # Ajouter les données au tampon
        self.data_buffer.extend(in_data)

        # Décoder les données si disponibles
        try:
            decoded_data = self.data_buffer.decode("utf-8", errors="ignore")
            # Créer un dictionnaire JSON
            message_dict = {"frame": {"dst_mac": 45, "priority": 1, "data": decoded_data}}
            json_message = json.dumps(message_dict)

            # Envoyer le message sous forme de PMT
            msg_pmt = pmt.intern(json_message)
            self.message_port_pub(pmt.intern("out"), msg_pmt)

            # Réinitialiser le tampon
            self.data_buffer = bytearray()
        except Exception as e:
            print(f"Erreur lors du décodage ou de l'envoi : {e}")

        return len(in_data)
