from pydantic import BaseModel


class Config(BaseModel):
    synth_params: list[str]
    max_ip: str
    max_send_port: int
    max_receive_port: int
    max_randomizations: int
    log_file_path: str
