from drimesyncunofficial.base_download_manager import BaseDownloadManager
from drimesyncunofficial.constants import COL_BLEU

class ManualDownloadManager(BaseDownloadManager):
    def show(self) -> None:
        super()._init_ui(title="DOWNLOAD MANUEL", title_color=COL_BLEU)