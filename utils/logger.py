import logging 

def init_logger():
    logging.basicConfig(
        filename='execution.log',  # Log file name
        filemode='a',        # Append mode
        format='%(asctime)s - %(levelname)s - %(filename)s - %(funcName)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO   # Minimum level to capture
    )

    # Add console logging too
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(filename)s - %(funcName)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)