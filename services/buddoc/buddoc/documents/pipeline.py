from docling.datamodel.document import ConversionResult
from docling.pipeline.vlm_pipeline import VlmPipeline


class DirectTextVlmPipeline(VlmPipeline):
    """Custom VLM pipeline that skips document assembly and returns raw text."""

    def _assemble_document(self, conv_res: ConversionResult) -> ConversionResult:
        """Override assembly to directly concatenate VLM text responses without parsing."""
        from docling_core.types.doc import DocItemLabel, DoclingDocument

        # Initialize a new document
        conv_res.document = DoclingDocument(name=conv_res.input.file.name)

        # Collect all text from all pages
        all_text = []

        # Process each page
        for page_idx, page in enumerate(conv_res.pages):
            if page.predictions.vlm_response and page.predictions.vlm_response.text:
                # Get the raw text from VLM
                text = page.predictions.vlm_response.text.strip()

                # Add page separator if not first page
                if page_idx > 0:
                    all_text.append(f"\n<!-- Page {page_idx + 1} -->\n")

                # Add the page text
                all_text.append(text)

        # Add all text as a single text item to avoid parsing
        if all_text:
            combined_text = "\n\n".join(all_text)
            # Use TEXT label for raw text content
            conv_res.document.add_text(label=DocItemLabel.TEXT, text=combined_text)

        return conv_res
