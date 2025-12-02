# Implementation of a channel monitor block in GNU Radio with Python
# This script creates a block to determine if the channel is free for communication.

from gnuradio import gr
import numpy as np

class ChannelMonitor(gr.sync_block):
    def __init__(self, frequency_mhz=0, bandwidth_hz=3000, sample_rate=32000, threshold=0.1):
        """
        Initialize the Channel Monitor block.
        :param frequency_mhz: Center frequency in MHz to monitor for energy detection.
        :param bandwidth_hz: Bandwidth in Hz to average energy over.
        :param sample_rate: Sampling rate of the input signal.
        :param threshold: Energy threshold to determine if the channel is busy.
        """
        gr.sync_block.__init__(
            self,
            name="ChannelMonitor",  # Name of the block
            in_sig=[np.complex64],  # Raw signal input for FFT
            out_sig=[np.float32]    # Output signal indicating if the channel is free (1) or busy (0)
        )

        self.frequency_mhz = frequency_mhz
        self.bandwidth_hz = bandwidth_hz
        self.sample_rate = sample_rate
        self.threshold = threshold

    def work(self, input_items, output_items):
        """
        Analyze the input signal to determine if the channel is free.
        :param input_items: Samples for FFT-based channel sensing.
        :param output_items: Output indicating if the channel is free (1) or busy (0).
        """
        input_signal = input_items[0]
        output_signal = output_items[0]

        # Validate input length
        if len(input_signal) == 0:
            raise ValueError("Input signal is empty!")

        # Compute the FFT and magnitude
        fft_size = len(input_signal)  # Use the length of the input signal
        energy = np.abs(np.fft.fft(input_signal))
        freqs = np.fft.fftfreq(fft_size, d=1 / self.sample_rate)

        # Calculate the bin index for the target frequency and bandwidth
        center_frequency_hz = self.frequency_mhz * 1e6
        if not (0 <= center_frequency_hz <= self.sample_rate / 2):
            raise ValueError(f"Frequency {self.frequency_mhz} MHz is out of range for the sample rate {self.sample_rate} Hz")

        half_bandwidth_bins = int((self.bandwidth_hz / 2) / (self.sample_rate / fft_size))
        center_bin = int((center_frequency_hz / self.sample_rate) * fft_size)

        # Ensure center_bin is within bounds
        if center_bin >= fft_size:
            center_bin = fft_size - 1

        # Determine the range of bins to average over
        start_bin = max(center_bin - half_bandwidth_bins, 0)
        end_bin = min(center_bin + half_bandwidth_bins, fft_size - 1)

        # Compute the average energy in the specified bandwidth
        avg_energy = np.mean(energy[start_bin:end_bin + 1])

        # Determine if the channel is free
        if avg_energy < self.threshold:
            #print(f"[ChannelMonitor] Channel at {self.frequency_mhz} MHz (±{self.bandwidth_hz/2} Hz) is FREE. Average Energy: {avg_energy}")
            output_signal[:] = 1.0  # Channel is free
        else:
            #print(f"[ChannelMonitor] Channel at {self.frequency_mhz} MHz (±{self.bandwidth_hz/2} Hz) is BUSY. Average Energy: {avg_energy}")
            output_signal[:] = 0.0  # Channel is busy

        return len(output_signal)
