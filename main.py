import csv
import logging
import random
import threading
import time
from typing import List

import yaml
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

from models import Config

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_config() -> Config:
    """
    Load configuration from config.yml file.

    Returns:
        Config: Configuration object with loaded settings.

    Raises:
        yaml.YAMLError: If the config file is malformed.
        FileNotFoundError: If config.yml is not found.
    """
    try:
        with open("config.yml", "r") as file:
            config = yaml.safe_load(file)
        return Config(**config)
    except FileNotFoundError:
        logger.error("Config file 'config.yml' not found")
        raise
    except yaml.YAMLError as e:
        logger.error("Error parsing config file: %s", e)
        raise


def log_synth_settings(address: str, *args, config: Config) -> None:
    """
    Log received synth settings to CSV file.

    Args:
        address: OSC address pattern
        *args: Variable length argument list containing synth parameters
        config: Configuration object containing settings
        param_names: List of parameter names for the synth
    """
    try:
        settings = list(args)[1:]  # Ignore the first value (from `t b`)

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        settings_dict = dict(zip(config.synth_params, settings))

        with open(config.log_file_path, "a", newline="") as f:
            fieldnames = ["Timestamp"] + config.synth_params
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow({"Timestamp": timestamp, **settings_dict})

        logger.debug("Logged synth settings: %s", settings_dict)
    except IOError as e:
        logger.error("Failed to write to %s: %s", config.log_file_path, e)
    except Exception as e:
        logger.error("Unexpected error while logging synth settings: %s", e)


def start_osc_server(config: Config) -> None:
    """
    Start OSC server in a separate thread.

    Args:
        config: Configuration object containing server settings
    """
    logger.info("Starting OSC Server...")
    try:
        dispatcher = Dispatcher()
        # Use lambda to properly pass keyword arguments
        dispatcher.map(
            "/synth_settings",
            lambda addr, *args: log_synth_settings(addr, *args, config=config),
        )

        server = BlockingOSCUDPServer(
            (config.max_ip, config.max_receive_port), dispatcher
        )
        logger.info(
            "Listening on %s:%s for synth settings",
            config.max_ip,
            config.max_receive_port,
        )
        server.serve_forever()
    except OSError as e:
        logger.error("Failed to start OSC server: %s", e)
        raise


def main() -> None:
    """Main function to run the application."""
    try:
        config = load_config()
        client = SimpleUDPClient(config.max_ip, config.max_send_port)

        server_thread = threading.Thread(
            target=start_osc_server, args=(config,), daemon=True
        )
        server_thread.start()

        # Main loop: trigger randomization every 1 second, max 100 times
        for i in range(config.max_randomizations):
            logger.info(
                "Sending Randomization Command to Max... (iteration %d/%d)",
                i + 1,
                config.max_randomizations,
            )
            random_value = random.randint(1, 100)
            try:
                client.send_message("/random", random_value)
                # Small delay to allow Max to process and respond
                time.sleep(0.01)
            except Exception as e:
                logger.error("Failed to send OSC message: %s", e)

        # Add a final delay to ensure all responses are processed
        logger.info("Waiting for final responses...")
        time.sleep(0.5)  # 500ms final delay
        logger.info("Done.")

    except KeyboardInterrupt:
        logger.info("Shutting down application...")
    except Exception as e:
        logger.error("Application error: %s", e)
        raise


if __name__ == "__main__":
    main()
