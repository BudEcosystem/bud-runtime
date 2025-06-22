"""Mock response generators for vLLM API endpoints."""

import asyncio
import random
import time
from typing import AsyncIterator, List, Union

from .protocol import (
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatCompletionStreamResponse,
    ChatCompletionStreamResponseChoice,
    ChatMessage,
    ClassificationResponse,
    ClassificationResponseData,
    CompletionResponse,
    CompletionResponseChoice,
    CompletionStreamResponse,
    CompletionStreamResponseChoice,
    DetokenizeResponse,
    EmbeddingResponse,
    EmbeddingResponseData,
    ModelCard,
    ModelList,
    ModelPermission,
    PoolingResponse,
    PoolingResponseData,
    RerankResponse,
    RerankResult,
    ScoreResponse,
    ScoreResponseData,
    TokenizeResponse,
    TranscriptionResponse,
    Usage,
)


# Sample responses for different types of completions
SAMPLE_COMPLETIONS = [
    "This is a sample response from the mock vLLM service.",
    "The mock service is designed for integration testing without actual model inference.",
    "It provides realistic responses with configurable delays to simulate processing time.",
    "You can use this service to test your application's integration with vLLM APIs.",
    "The responses are deterministic based on the input for easier testing.",
]

SAMPLE_CHAT_RESPONSES = [
    "I understand your request. This is a mock response from the vLLM service.",
    "Thank you for your message. The mock service is responding appropriately.",
    "I'm here to help with your testing needs. This response simulates a real LLM.",
    "Your integration test is working correctly with the mock vLLM service.",
    "This demonstrates that the API endpoint is functioning as expected.",
]


class MockResponseGenerator:
    """Generates mock responses for vLLM API endpoints."""
    
    def __init__(self, processing_delay: float = 0.1):
        self.processing_delay = processing_delay
        self.models = [
            "mock-gpt-3.5-turbo",
            "mock-gpt-4",
            "mock-llama-2-7b",
            "mock-mistral-7b",
            "mock-embedding-model",
            "mock-rerank-model",
            "mock-transcription-model",
        ]
    
    async def simulate_processing(self, factor: float = 1.0):
        """Simulate processing time."""
        await asyncio.sleep(self.processing_delay * factor)
    
    def get_model_list(self) -> ModelList:
        """Generate list of available models."""
        data = []
        for model_id in self.models:
            card = ModelCard(
                id=model_id,
                permission=[ModelPermission()],
                max_model_len=4096 if "embedding" not in model_id else None
            )
            data.append(card)
        return ModelList(data=data)
    
    async def generate_chat_completion(
        self, request: dict, stream: bool = False
    ) -> Union[ChatCompletionResponse, AsyncIterator[str]]:
        """Generate mock chat completion response."""
        model = request.get("model", "mock-gpt-3.5-turbo")
        messages = request.get("messages", [])
        
        # Select response based on message count
        response_text = SAMPLE_CHAT_RESPONSES[len(messages) % len(SAMPLE_CHAT_RESPONSES)]
        
        if stream:
            return self._stream_chat_response(model, response_text)
        else:
            await self.simulate_processing()
            
            response = ChatCompletionResponse(
                model=model,
                choices=[
                    ChatCompletionResponseChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content=response_text),
                        finish_reason="stop"
                    )
                ],
                usage=Usage(
                    prompt_tokens=len(str(messages)) // 4,
                    completion_tokens=len(response_text) // 4,
                    total_tokens=(len(str(messages)) + len(response_text)) // 4
                )
            )
            return response
    
    async def _stream_chat_response(self, model: str, text: str) -> AsyncIterator[str]:
        """Stream chat completion response."""
        # Initial chunk
        response = ChatCompletionStreamResponse(
            model=model,
            choices=[
                ChatCompletionStreamResponseChoice(
                    index=0,
                    delta=ChatMessage(role="assistant", content=""),
                    finish_reason=None
                )
            ]
        )
        yield f"data: {response.model_dump_json()}\n\n"
        
        # Stream text in chunks
        words = text.split()
        for i, word in enumerate(words):
            await self.simulate_processing(0.02)
            
            response = ChatCompletionStreamResponse(
                model=model,
                choices=[
                    ChatCompletionStreamResponseChoice(
                        index=0,
                        delta=ChatMessage(role=None, content=word + " "),
                        finish_reason=None
                    )
                ]
            )
            yield f"data: {response.model_dump_json()}\n\n"
        
        # Final chunk
        response = ChatCompletionStreamResponse(
            model=model,
            choices=[
                ChatCompletionStreamResponseChoice(
                    index=0,
                    delta=ChatMessage(role=None, content=None),
                    finish_reason="stop"
                )
            ]
        )
        yield f"data: {response.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"
    
    async def generate_completion(
        self, request: dict, stream: bool = False
    ) -> Union[CompletionResponse, AsyncIterator[str]]:
        """Generate mock text completion response."""
        model = request.get("model", "mock-gpt-3.5-turbo")
        prompt = request.get("prompt", "")
        
        if isinstance(prompt, list):
            prompt = prompt[0] if prompt else ""
        
        # Select response based on prompt length
        response_text = SAMPLE_COMPLETIONS[len(prompt) % len(SAMPLE_COMPLETIONS)]
        
        if stream:
            return self._stream_completion_response(model, response_text)
        else:
            await self.simulate_processing()
            
            response = CompletionResponse(
                model=model,
                choices=[
                    CompletionResponseChoice(
                        text=response_text,
                        index=0,
                        finish_reason="stop"
                    )
                ],
                usage=Usage(
                    prompt_tokens=len(prompt) // 4,
                    completion_tokens=len(response_text) // 4,
                    total_tokens=(len(prompt) + len(response_text)) // 4
                )
            )
            return response
    
    async def _stream_completion_response(self, model: str, text: str) -> AsyncIterator[str]:
        """Stream text completion response."""
        words = text.split()
        for i, word in enumerate(words):
            await self.simulate_processing(0.02)
            
            response = CompletionStreamResponse(
                model=model,
                choices=[
                    CompletionStreamResponseChoice(
                        text=word + " ",
                        index=0,
                        finish_reason=None if i < len(words) - 1 else "stop"
                    )
                ]
            )
            yield f"data: {response.model_dump_json()}\n\n"
        
        yield "data: [DONE]\n\n"
    
    async def generate_embedding(self, request: dict) -> EmbeddingResponse:
        """Generate mock embedding response."""
        model = request.get("model", "mock-embedding-model")
        input_data = request.get("input", "")
        
        await self.simulate_processing(0.5)
        
        # Handle different input types
        if isinstance(input_data, str):
            inputs = [input_data]
        elif isinstance(input_data, list):
            inputs = input_data if all(isinstance(x, str) for x in input_data) else [""]
        else:
            inputs = [""]
        
        # Generate mock embeddings
        data = []
        for i, inp in enumerate(inputs):
            # Generate deterministic embedding based on input
            random.seed(hash(inp) % 1000000)
            embedding = [random.random() for _ in range(768)]  # 768-dimensional embedding
            data.append(
                EmbeddingResponseData(
                    index=i,
                    embedding=embedding
                )
            )
        
        response = EmbeddingResponse(
            data=data,
            model=model,
            usage=Usage(
                prompt_tokens=sum(len(inp) // 4 for inp in inputs),
                completion_tokens=0,
                total_tokens=sum(len(inp) // 4 for inp in inputs)
            )
        )
        return response
    
    async def tokenize(self, request: dict) -> TokenizeResponse:
        """Generate mock tokenization response."""
        prompt = request.get("prompt", "")
        
        await self.simulate_processing(0.05)
        
        # Simple mock tokenization (4 chars per token on average)
        tokens = list(range(1000, 1000 + len(prompt) // 4))
        
        return TokenizeResponse(
            tokens=tokens,
            count=len(tokens)
        )
    
    async def detokenize(self, request: dict) -> DetokenizeResponse:
        """Generate mock detokenization response."""
        tokens = request.get("tokens", [])
        
        await self.simulate_processing(0.05)
        
        # Simple mock detokenization
        prompt = f"Detokenized text from {len(tokens)} tokens"
        
        return DetokenizeResponse(prompt=prompt)
    
    async def generate_pooling(self, request: dict) -> PoolingResponse:
        """Generate mock pooling response."""
        model = request.get("model", "mock-gpt-3.5-turbo")
        prompt = request.get("prompt", "")
        
        await self.simulate_processing(0.3)
        
        if isinstance(prompt, str):
            prompts = [prompt]
        else:
            prompts = prompt
        
        # Generate mock pooled embeddings
        data = []
        for i, p in enumerate(prompts):
            random.seed(hash(p) % 1000000)
            embedding = [random.random() for _ in range(768)]
            data.append(
                PoolingResponseData(
                    index=i,
                    embedding=embedding
                )
            )
        
        response = PoolingResponse(
            data=data,
            model=model,
            usage=Usage(
                prompt_tokens=sum(len(p) // 4 for p in prompts),
                completion_tokens=0,
                total_tokens=sum(len(p) // 4 for p in prompts)
            )
        )
        return response
    
    async def generate_score(self, request: dict) -> ScoreResponse:
        """Generate mock score response."""
        model = request.get("model", "mock-gpt-3.5-turbo")
        text_1 = request.get("text_1", "")
        text_2 = request.get("text_2", "")
        
        await self.simulate_processing(0.2)
        
        # Ensure lists
        if isinstance(text_1, str):
            text_1 = [text_1]
        if isinstance(text_2, str):
            text_2 = [text_2]
        
        # Generate mock scores
        data = []
        for i in range(max(len(text_1), len(text_2))):
            t1 = text_1[i % len(text_1)]
            t2 = text_2[i % len(text_2)]
            
            # Generate deterministic score based on texts
            random.seed(hash(t1 + t2) % 1000000)
            score = random.random()
            
            data.append(
                ScoreResponseData(
                    index=i,
                    score=score
                )
            )
        
        response = ScoreResponse(
            data=data,
            model=model,
            usage=Usage(
                prompt_tokens=(sum(len(t) // 4 for t in text_1) + 
                              sum(len(t) // 4 for t in text_2)),
                completion_tokens=0,
                total_tokens=(sum(len(t) // 4 for t in text_1) + 
                             sum(len(t) // 4 for t in text_2))
            )
        )
        return response
    
    async def generate_classification(self, request: dict) -> ClassificationResponse:
        """Generate mock classification response."""
        model = request.get("model", "mock-gpt-3.5-turbo")
        prompt = request.get("prompt", "")
        labels = request.get("labels", ["positive", "negative", "neutral"])
        
        await self.simulate_processing(0.2)
        
        if isinstance(prompt, str):
            prompts = [prompt]
        else:
            prompts = prompt
        
        # Generate mock classifications
        data = []
        for i, p in enumerate(prompts):
            # Select label based on prompt
            random.seed(hash(p) % 1000000)
            label = random.choice(labels)
            score = random.uniform(0.7, 0.99)
            
            data.append(
                ClassificationResponseData(
                    index=i,
                    label=label,
                    score=score
                )
            )
        
        response = ClassificationResponse(
            data=data,
            model=model,
            usage=Usage(
                prompt_tokens=sum(len(p) // 4 for p in prompts),
                completion_tokens=0,
                total_tokens=sum(len(p) // 4 for p in prompts)
            )
        )
        return response
    
    async def generate_rerank(self, request: dict) -> RerankResponse:
        """Generate mock rerank response."""
        model = request.get("model", "mock-rerank-model")
        query = request.get("query", "")
        documents = request.get("documents", [])
        top_n = request.get("top_n", len(documents))
        return_documents = request.get("return_documents", True)
        
        await self.simulate_processing(0.3)
        
        # Process documents
        doc_texts = []
        for i, doc in enumerate(documents):
            if isinstance(doc, str):
                doc_texts.append((i, doc, None))
            else:
                doc_texts.append((i, doc.get("text", ""), doc.get("meta", None)))
        
        # Generate scores and sort
        scored_docs = []
        for idx, text, meta in doc_texts:
            random.seed(hash(query + text) % 1000000)
            score = random.random()
            scored_docs.append((idx, text, meta, score))
        
        # Sort by score descending and take top_n
        scored_docs.sort(key=lambda x: x[3], reverse=True)
        scored_docs = scored_docs[:top_n]
        
        # Create results
        results = []
        for idx, text, meta, score in scored_docs:
            result = RerankResult(
                index=idx,
                relevance_score=score,
                text=text if return_documents else None,
                meta=meta if return_documents and meta else None
            )
            results.append(result)
        
        response = RerankResponse(
            model=model,
            results=results,
            usage=Usage(
                prompt_tokens=len(query) // 4 + sum(len(t) // 4 for _, t, _ in doc_texts),
                completion_tokens=0,
                total_tokens=len(query) // 4 + sum(len(t) // 4 for _, t, _ in doc_texts)
            )
        )
        return response
    
    async def generate_transcription(self, audio_data: bytes, request: dict) -> TranscriptionResponse:
        """Generate mock transcription response."""
        await self.simulate_processing(1.0)  # Simulate longer processing for audio
        
        # Generate mock transcription based on file size
        file_size_kb = len(audio_data) / 1024
        duration_seconds = int(file_size_kb / 10)  # Rough estimate
        
        transcription = f"This is a mock transcription of approximately {duration_seconds} seconds of audio. The mock vLLM service has successfully processed the audio file."
        
        return TranscriptionResponse(text=transcription)