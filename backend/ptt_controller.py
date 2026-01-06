"""
PTT Controller for HAMSTR

Manual PTT control for radios when using VARA HF.
VARA HF requires the host application to control PTT.

Supports serial RTS, DTR, or BOTH control methods.

Usage:
    from ptt_controller import PTTController
    
    ptt = PTTController('COM11', baud=38400, method='BOTH')
    ptt.connect()
    ptt.key()      # Key radio
    time.sleep(1)
    ptt.unkey()    # Unkey radio
    ptt.disconnect()
"""

import serial
import logging
import time
from typing import Optional

class PTTController:
    """
    Serial PTT controller using RTS, DTR, or both pins.
    
    Provides manual PTT control for radios.
    Required for VARA HF operation.
    """
    
    def __init__(self, 
                 port: str,
                 baud: int = 9600,
                 method: str = 'RTS',
                 pre_delay: float = 0.1,
                 post_delay: float = 0.1):
        """
        Initialize PTT controller.
        
        Args:
            port: Serial port (e.g., 'COM11', '/dev/ttyUSB0')
            baud: Baud rate (9600, 19200, 38400, etc.)
            method: 'RTS', 'DTR', or 'BOTH' - which pin(s) to use for PTT
            pre_delay: Seconds to hold PTT before transmitting (radio stabilization)
            post_delay: Seconds to hold PTT after transmission done (tail delay)
        """
        self.port = port
        self.baud = baud
        self.method = method.upper()
        self.pre_delay = pre_delay
        self.post_delay = post_delay
        self.serial: Optional[serial.Serial] = None
        self.is_keyed = False
        
        if self.method not in ['RTS', 'DTR', 'BOTH']:
            raise ValueError("PTT method must be 'RTS', 'DTR', or 'BOTH'")
        
        logging.info(f"[PTT] Initializing PTT controller on {port} @ {baud} baud using {method}")
        
    def connect(self) -> bool:
        """Open serial port for PTT control."""
        try:
            logging.info(f"[PTT] Attempting to open {self.port} @ {self.baud} baud")
            
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=1,
                rtscts=False,
                dsrdtr=False,
                exclusive=True  # Add this - prevents other apps from sharing
            )
            
            logging.info(f"[PTT] Port opened successfully")
            
            # Initialize PTT to off
            self.unkey()
            
            logging.info(f"[PTT] Connected to {self.port}")
            return True
            
        except Exception as e:
            logging.error(f"[PTT] Failed to connect: {e}")
            import traceback
            logging.error(traceback.format_exc())  # Get full error details
            self.serial = None
            return False
    
    def key(self) -> bool:
        """
        Key the radio (PTT on).
        
        Returns:
            True if successful
        """
        if not self.serial or not self.serial.is_open:
            logging.warning("[PTT] Cannot key - serial port not open")
            return False
        
        try:
            # Assert appropriate pin(s)
            if self.method == 'RTS':
                self.serial.setRTS(True)
            elif self.method == 'DTR':
                self.serial.setDTR(True)
            elif self.method == 'BOTH':
                self.serial.setRTS(True)
                self.serial.setDTR(True)
            
            self.is_keyed = True
            logging.debug(f"[PTT] Radio keyed via {self.method}")
            
            # Pre-PTT delay to let radio stabilize
            if self.pre_delay > 0:
                time.sleep(self.pre_delay)
            
            return True
            
        except Exception as e:
            logging.error(f"[PTT] Failed to key radio: {e}")
            return False
    
    def unkey(self) -> bool:
        """
        Unkey the radio (PTT off).
        
        Returns:
            True if successful
        """
        if not self.serial or not self.serial.is_open:
            logging.warning("[PTT] Cannot unkey - serial port not open")
            return False
        
        try:
            # Post-PTT delay to ensure transmission completes
            if self.is_keyed and self.post_delay > 0:
                time.sleep(self.post_delay)
            
            # De-assert appropriate pin(s)
            if self.method == 'RTS':
                self.serial.setRTS(False)
            elif self.method == 'DTR':
                self.serial.setDTR(False)
            elif self.method == 'BOTH':
                self.serial.setRTS(False)
                self.serial.setDTR(False)
            
            self.is_keyed = False
            logging.debug(f"[PTT] Radio unkeyed via {self.method}")
            return True
            
        except Exception as e:
            logging.error(f"[PTT] Failed to unkey radio: {e}")
            return False
    
    def disconnect(self):
        """Close serial port and ensure PTT is off."""
        if self.serial and self.serial.is_open:
            try:
                # Ensure PTT is off before closing
                self.unkey()
                self.serial.close()
                logging.info("[PTT] Disconnected")
            except Exception as e:
                logging.error(f"[PTT] Error during disconnect: {e}")
        
        self.serial = None
    
    def __enter__(self):
        """Context manager support."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support."""
        self.disconnect()


# Test function for standalone testing
if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: python ptt_controller.py <COM_PORT> [baud] [method]")
        print("Example: python ptt_controller.py COM11 38400 BOTH")
        sys.exit(1)
    
    port = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 38400
    method = sys.argv[3] if len(sys.argv) > 3 else 'BOTH'
    
    print(f"\nTesting PTT on {port} @ {baud} baud using {method}")
    print("Watch for transmit LED or power meter...")
    
    with PTTController(port, baud, method) as ptt:
        print("\nKeying radio for 2 seconds...")
        ptt.key()
        time.sleep(2)
        print("Unkeying radio...")
        ptt.unkey()
        print("\nTest complete!")