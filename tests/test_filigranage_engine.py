
import pytest
from unittest.mock import MagicMock, patch, ANY
import os
from drimesyncunofficial.filigranage_engine import OmegaEngine

class TestOmegaEngine:
    
    @pytest.fixture
    def engine(self):
        return OmegaEngine(log_callback=MagicMock())

    def test_generate_qr_code(self, engine):
        data = {"test": "data"}
        with patch('drimesyncunofficial.filigranage_engine.qrcode') as mock_qr, \
             patch('drimesyncunofficial.filigranage_engine.StyledPilImage'), \
             patch('drimesyncunofficial.filigranage_engine.RoundedModuleDrawer'):
            mock_qr_obj = MagicMock()
            mock_qr.QRCode.return_value = mock_qr_obj
            mock_img = MagicMock()
            mock_img.getdata.return_value = [(0,0,0,0)] 
            # Handle .convert("RGBA") chain
            mock_converted_img = MagicMock()
            mock_img.convert.return_value = mock_converted_img
            
            mock_qr_obj.make_image.return_value = mock_img
            
            result = engine.generate_qr_code(data)
            
            assert result is mock_converted_img
            mock_qr.QRCode.assert_called()

    def test_process_image_success(self, engine):
        input_path = "test.jpg"
        output_path = "test_SECURE.jpg"
        data = {"doc_hash": "123", "uuid": "abc", "to": "TEST", "ts": "2023", "author": "me"}
        qr_img = MagicMock()
        qr_img.resize.return_value = MagicMock()
        options = {"microprint": True, "anti_copy": True, "mesh": True, "crypto_link": True, "qr_triangulation": True}
        
        with patch("PIL.Image.open") as mock_open, \
             patch("PIL.ImageOps.exif_transpose") as mock_transpose, \
             patch("PIL.Image.new") as mock_new, \
             patch("PIL.ImageDraw.Draw") as mock_draw, \
             patch("PIL.Image.alpha_composite") as mock_composite, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=123):
             
             mock_base = MagicMock()
             mock_base.size = (1000, 1000)
             mock_base.info = {}
             mock_transpose.return_value.convert.return_value = mock_base
             
             # Fix for rotate().size unpacking
             mock_tile = MagicMock()
             mock_new.return_value = mock_tile
             # When recursive calls return new mocks, ensure they have .size
             mock_rotated = MagicMock()
             mock_rotated.size = (100, 100)
             mock_tile.rotate.return_value = mock_rotated
             
             engine.process_image(input_path, output_path, data, qr_img, options)
             
             # Verify save called
             mock_composite.return_value.convert.return_value.save.assert_called_with(output_path, "JPEG", quality=100, subsampling=0, exif=ANY)

    def test_process_pdf_success(self, engine):
        input_path = "test.pdf"
        output_path = "test_SECURE.pdf"
        data = {"doc_hash": "123", "uuid": "abc", "to": "TEST", "ts": "2023", "author": "me", "user_pwd": "pwd"}
        qr_img = MagicMock()
        options = {"microprint": True, "anti_copy": True, "mesh": True, "crypto_link": True}
        
        with patch("drimesyncunofficial.filigranage_engine.PdfReader") as mock_reader, \
             patch("drimesyncunofficial.filigranage_engine.PdfWriter") as mock_writer, \
             patch("drimesyncunofficial.filigranage_engine.canvas") as mock_canvas_mod, \
             patch("drimesyncunofficial.filigranage_engine.ImageReader") as mock_image_reader, \
             patch("drimesyncunofficial.filigranage_engine.Color"), \
             patch("builtins.open", new_callable=MagicMock) as mock_file, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=456):
             
             # Setup PDF pages
             mock_page = MagicMock()
             mock_page.mediabox.width = 100
             mock_page.mediabox.height = 100
             mock_reader.return_value.pages = [mock_page]
             
             engine.process_pdf(input_path, output_path, data, qr_img, options)
             
             # Verify writer actions
             mock_writer.return_value.add_page.assert_called()
             mock_writer.return_value.encrypt.assert_called()
             mock_writer.return_value.write.assert_called()
