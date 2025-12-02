from gnuradio import gr
import pmt
import numpy as np


class ichar_to_pmt(gr.sync_block):
    """
    Bloc GNU Radio pour transformer un flux de caractères signés (int8) en un message PMT
    """

    def __init__(self):
        # Initialisation du bloc
        gr.sync_block.__init__(
            self,
            name="Ichar to PMT",
            in_sig=[np.int8],  # Entrée sous forme de flux de caractères signés
            out_sig=[]  # Pas de sortie de flux
        )
        # Enregistrement d'une porte de sortie pour envoyer des messages PMT
        self.message_port_register_out(pmt.intern("out"))
        # Initialisation du tampon avec une chaîne binaire vide
        self.data_buffer = bytearray()  # Utilisation de bytearray pour gérer les données binaires

    def work(self, input_items, output_items):
        """
        Lire les données en entrée et envoyer un message PMT
        """
        # Lire les données d'entrée
        in_data = input_items[0]

        # Convertir les entiers signés (-128 à 127) en valeurs non signées (0 à 255)
        unsigned_data = (in_data.astype(np.uint8))

        # Ajouter les données converties au tampon
        self.data_buffer.extend(unsigned_data)

        # Si le tampon contient des données, envoyer un message PMT
        if len(self.data_buffer) > 0:
            try:
                # Convertir en représentation hexadécimale pour les données binaires
                hex_data = ' '.join([f'{x:02x}' for x in self.data_buffer])
                #print(f"Converted hex data: {hex_data}")

                # Créer un message PMT contenant les données hexadécimales
                msg_pmt = pmt.intern(hex_data)
                
                # Envoyer le message via la porte de sortie
                self.message_port_pub(pmt.intern("out"), msg_pmt)
                
                # Réinitialiser le tampon après l'envoi
                self.data_buffer = bytearray()
            except Exception as e:
                print(f"Erreur lors du décodage ou de l'envoi du message : {e}")

        return len(in_data)

