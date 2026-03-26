import unittest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory, SimpleTestCase
from django.http import Http404, HttpResponseRedirect
from callcenter.views import generate_ticket_pdf_view

class TicketPDFViewTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('callcenter.views.SolicitudTicket')
    @patch('callcenter.views.save_ticket_pdf_helper')
    def test_generate_ticket_pdf_view_redirects(self, mock_helper, mock_model):
        # Configurar mocks
        mock_ticket = MagicMock()
        mock_model.objects.filter.return_value.first.return_value = mock_ticket
        
        dummy_url = "http://testserver/media/test.pdf"
        mock_helper.return_value = dummy_url
        
        # Crear la petición
        request = self.factory.get('/callcenter/api/ticket/SS26-123456/pdf/')
        
        # Llamar a la vista
        response = generate_ticket_pdf_view(request, folio="SS26-123456")
        
        # Verificar que es un redireccionamiento
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, dummy_url)
        mock_helper.assert_called_once_with(mock_ticket, request=request)

    @patch('callcenter.views.SolicitudTicket')
    def test_generate_ticket_pdf_view_404(self, mock_model):
        # Configurar mock para que no encuentre nada
        mock_model.objects.filter.return_value.first.return_value = None
        
        request = self.factory.get('/callcenter/api/ticket/NONEXISTENT/pdf/')
        with self.assertRaises(Http404):
            generate_ticket_pdf_view(request, folio="NONEXISTENT")
