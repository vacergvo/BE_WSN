from gnuradio import gr
import pmt
import numpy as np


class pmt_to_ichar(gr.sync_block):
    """
    Bloc GNU Radio pour transformer un message PMT en un flux d'entiers (int8)
    """

    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="PMT to Ichar",
            in_sig=[],
            out_sig=[np.int8],
        )
        self.message_port_register_in(pmt.intern("in"))
        self.set_msg_handler(pmt.intern("in"), self.handle_msg)
        self.data_queue = bytearray()

    def handle_msg(self, msg_pmt):
        try:
            # Vérifier si le message PMT contient une chaîne
            if pmt.is_pair(msg_pmt):
                msg_str = pmt.to_python(pmt.cdr(msg_pmt))
                if isinstance(msg_str, str):
                    self.data_queue.extend(msg_str.encode("utf-8"))
        except Exception as e:
            print(f"Erreur dans handle_msg : {e}")

    def work(self, input_items, output_items):
        out = output_items[0]
        length = min(len(out), len(self.data_queue))
        out[:length] = np.frombuffer(self.data_queue[:length], dtype=np.int8)
        self.data_queue = self.data_queue[length:]
        return length
