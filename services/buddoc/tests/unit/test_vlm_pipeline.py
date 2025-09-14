"""Unit tests for VLM pipeline."""

from unittest.mock import Mock, MagicMock, patch

import pytest

from buddoc.documents.pipeline import DirectTextVlmPipeline


class TestDirectTextVlmPipeline:
    """Test cases for DirectTextVlmPipeline."""

    @pytest.fixture
    def pipeline(self):
        """Create pipeline instance without full initialization."""
        # Create the pipeline instance directly without going through __init__
        pipeline = object.__new__(DirectTextVlmPipeline)
        return pipeline

    @pytest.fixture
    def mock_conversion_result(self):
        """Create mock conversion result."""
        conv_res = Mock()
        conv_res.input = Mock()
        conv_res.input.file = Mock()
        conv_res.input.file.name = "test.pdf"
        conv_res.pages = []
        conv_res.document = None
        return conv_res

    def test_assemble_document_method_exists(self, pipeline):
        """Test that _assemble_document method exists."""
        assert hasattr(pipeline, '_assemble_document')
        assert callable(getattr(pipeline, '_assemble_document'))

    @patch('docling_core.types.doc.DoclingDocument')
    def test_assemble_document_empty_pages(self, mock_doc_class, pipeline, mock_conversion_result):
        """Test assembling document with no pages."""
        mock_doc = Mock()
        mock_doc_class.return_value = mock_doc

        mock_conversion_result.pages = []

        result = pipeline._assemble_document(mock_conversion_result)

        # Should create a new document
        mock_doc_class.assert_called_once_with(name="test.pdf")
        assert result.document == mock_doc

    @patch('docling_core.types.doc.DoclingDocument')
    @patch('docling_core.types.doc.DocItemLabel')
    def test_assemble_document_single_page(self, mock_label, mock_doc_class, pipeline, mock_conversion_result):
        """Test assembling document with single page."""
        mock_doc = Mock()
        mock_doc_class.return_value = mock_doc
        mock_label.TEXT = 'text'

        # Create mock page with VLM response
        mock_page = Mock()
        mock_page.predictions = Mock()
        mock_page.predictions.vlm_response = Mock()
        mock_page.predictions.vlm_response.text = "Page 1 content"

        mock_conversion_result.pages = [mock_page]

        result = pipeline._assemble_document(mock_conversion_result)

        # Should add text to document
        mock_doc.add_text.assert_called_once_with(
            label='text',
            text="Page 1 content"
        )

    @patch('docling_core.types.doc.DoclingDocument')
    @patch('docling_core.types.doc.DocItemLabel')
    def test_assemble_document_multiple_pages(self, mock_label, mock_doc_class, pipeline, mock_conversion_result):
        """Test assembling document with multiple pages."""
        mock_doc = Mock()
        mock_doc_class.return_value = mock_doc
        mock_label.TEXT = 'text'

        # Create mock pages with VLM responses
        mock_pages = []
        for i in range(3):
            page = Mock()
            page.predictions = Mock()
            page.predictions.vlm_response = Mock()
            page.predictions.vlm_response.text = f"Page {i+1} content"
            mock_pages.append(page)

        mock_conversion_result.pages = mock_pages

        result = pipeline._assemble_document(mock_conversion_result)

        # Should combine all pages with separators
        expected_text = "Page 1 content\n\n\n<!-- Page 2 -->\n\n\nPage 2 content\n\n\n<!-- Page 3 -->\n\n\nPage 3 content"
        mock_doc.add_text.assert_called_once_with(
            label='text',
            text=expected_text
        )

    @patch('docling_core.types.doc.DoclingDocument')
    def test_assemble_document_no_vlm_response(self, mock_doc_class, pipeline, mock_conversion_result):
        """Test handling pages without VLM response."""
        mock_doc = Mock()
        mock_doc_class.return_value = mock_doc

        # Create mock page without VLM response
        mock_page = Mock()
        mock_page.predictions = Mock()
        mock_page.predictions.vlm_response = None

        mock_conversion_result.pages = [mock_page]

        result = pipeline._assemble_document(mock_conversion_result)

        # Should create document but not add text
        mock_doc_class.assert_called_once_with(name="test.pdf")
        mock_doc.add_text.assert_not_called()

    @patch('docling_core.types.doc.DoclingDocument')
    def test_assemble_document_empty_text(self, mock_doc_class, pipeline, mock_conversion_result):
        """Test handling empty VLM response text."""
        mock_doc = Mock()
        mock_doc_class.return_value = mock_doc

        # Create mock page with empty text
        mock_page = Mock()
        mock_page.predictions = Mock()
        mock_page.predictions.vlm_response = Mock()
        mock_page.predictions.vlm_response.text = "  \n  "

        mock_conversion_result.pages = [mock_page]

        result = pipeline._assemble_document(mock_conversion_result)

        # Should create document and add empty text (pipeline doesn't check if stripped text is empty)
        mock_doc_class.assert_called_once_with(name="test.pdf")
        mock_doc.add_text.assert_called_once()

    @patch('docling_core.types.doc.DoclingDocument')
    @patch('docling_core.types.doc.DocItemLabel')
    def test_assemble_document_page_separator(self, mock_label, mock_doc_class, pipeline, mock_conversion_result):
        """Test that page separators are added between pages."""
        mock_doc = Mock()
        mock_doc_class.return_value = mock_doc
        mock_label.TEXT = 'text'

        # Create two pages
        pages = []
        for i in range(2):
            page = Mock()
            page.predictions = Mock()
            page.predictions.vlm_response = Mock()
            page.predictions.vlm_response.text = f"Content {i+1}"
            pages.append(page)

        mock_conversion_result.pages = pages

        result = pipeline._assemble_document(mock_conversion_result)

        # Check that page separator is included
        expected_text = "Content 1\n\n\n<!-- Page 2 -->\n\n\nContent 2"
        mock_doc.add_text.assert_called_once_with(
            label='text',
            text=expected_text
        )

    @patch('docling_core.types.doc.DoclingDocument')
    @patch('docling_core.types.doc.DocItemLabel')
    def test_assemble_document_strips_whitespace(self, mock_label, mock_doc_class, pipeline, mock_conversion_result):
        """Test that text is stripped of whitespace."""
        mock_doc = Mock()
        mock_doc_class.return_value = mock_doc
        mock_label.TEXT = 'text'

        # Create mock page with whitespace
        mock_page = Mock()
        mock_page.predictions = Mock()
        mock_page.predictions.vlm_response = Mock()
        mock_page.predictions.vlm_response.text = "  Content with spaces  \n\n"

        mock_conversion_result.pages = [mock_page]

        result = pipeline._assemble_document(mock_conversion_result)

        # Text should be stripped
        mock_doc.add_text.assert_called_once_with(
            label='text',
            text="Content with spaces"
        )

    @patch('docling_core.types.doc.DoclingDocument')
    @patch('docling_core.types.doc.DocItemLabel')
    def test_assemble_document_mixed_pages(self, mock_label, mock_doc_class, pipeline, mock_conversion_result):
        """Test handling mixed pages (some with content, some without)."""
        mock_doc = Mock()
        mock_doc_class.return_value = mock_doc
        mock_label.TEXT = 'text'

        # Create pages with mixed content
        page1 = Mock()
        page1.predictions = Mock()
        page1.predictions.vlm_response = Mock()
        page1.predictions.vlm_response.text = "Page 1"

        page2 = Mock()
        page2.predictions = Mock()
        page2.predictions.vlm_response = None  # No response

        page3 = Mock()
        page3.predictions = Mock()
        page3.predictions.vlm_response = Mock()
        page3.predictions.vlm_response.text = "Page 3"

        mock_conversion_result.pages = [page1, page2, page3]

        result = pipeline._assemble_document(mock_conversion_result)

        # Should only include pages with content
        # Page 3 still gets labeled as Page 3 since it's at index 2
        expected_text = "Page 1\n\n\n<!-- Page 3 -->\n\n\nPage 3"
        mock_doc.add_text.assert_called_once_with(
            label='text',
            text=expected_text
        )

    def test_direct_text_vlm_pipeline_inheritance(self):
        """Test that DirectTextVlmPipeline inherits from VlmPipeline."""
        from docling.pipeline.vlm_pipeline import VlmPipeline
        assert issubclass(DirectTextVlmPipeline, VlmPipeline)