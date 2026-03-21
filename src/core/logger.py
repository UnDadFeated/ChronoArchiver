import logging
import os
import sys
from version import __version__

def setup_logger():
    # Reset handlers if re-initialized
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    # User requested NO LOG FILE. 
    # We only log to console (which is hidden in GUI mode unless debugged)
    
    # Secure log file path in AppData to prevent PermissionError
    log_dir = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'MediaArchiveOrganizer')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'media_organizer.log')
    
    handlers = [
        logging.FileHandler(log_file, mode='a', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]

    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        level=logging.INFO,
        handlers=handlers
    )
    
    # Explicit connection to stdout just in case basicConfig didn't pick it up (it usually does if no filename)
    # console = logging.StreamHandler()
    # console.setLevel(logging.DEBUG)
    # logging.getLogger('').addHandler(console)
    
    logging.info(f"=== Application Started ({__version__}) ===")
    
    return logging.getLogger('MediaOrganizer')
