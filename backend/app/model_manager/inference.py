"""
Inference engine — runs prediction on the loaded model.
Handles all 34+ AutoModel task types with appropriate
input processing and output formatting.
"""

import time
import logging
import base64
from io import BytesIO
from pathlib import Path
from typing import Optional, Any

import torch
from PIL import Image

from .config import ModelTaskType
from .loader import ModelLoader
from .schemas import InferenceRequest, InferenceResponse

logger = logging.getLogger("sovereign.inference")


class InferenceEngine:
    """
    Runs inference on the currently loaded model.
    Dispatches to appropriate handler based on task type.
    """
    
    def __init__(self):
        self.loader = ModelLoader()
    
    def run(self, request: InferenceRequest) -> InferenceResponse:
        """
        Run inference on loaded model.
        Dispatches based on task type.
        """
        if not self.loader.is_loaded:
            raise RuntimeError(
                "No model loaded. Load a model first."
            )
        
        task_type = self.loader.loaded_task_type
        model_id = self.loader.loaded_model_id
        
        start_time = time.time()
        
        # Dispatch to appropriate handler
        handler = self._get_handler(task_type)
        output, tokens_generated = handler(request)
        
        inference_time = (time.time() - start_time) * 1000
        
        return InferenceResponse(
            output=output,
            model_id=model_id,
            task_type=task_type.value,
            inference_time_ms=round(inference_time, 2),
            tokens_generated=tokens_generated,
        )
    
    def _get_handler(self, task_type: ModelTaskType):
        """Get the appropriate inference handler."""
        handlers = {
            ModelTaskType.CAUSAL_LM: self._causal_lm,
            ModelTaskType.MASKED_LM: self._masked_lm,
            ModelTaskType.SEQ2SEQ_LM: self._seq2seq_lm,
            ModelTaskType.SEQUENCE_CLASSIFICATION: self._seq_cls,
            ModelTaskType.TOKEN_CLASSIFICATION: self._token_cls,
            ModelTaskType.QUESTION_ANSWERING: self._qa,
            ModelTaskType.MULTIPLE_CHOICE: self._multiple_choice,
            ModelTaskType.IMAGE_CLASSIFICATION: self._image_cls,
            ModelTaskType.OBJECT_DETECTION: self._object_detection,
            ModelTaskType.SEMANTIC_SEGMENTATION: self._semantic_seg,
            ModelTaskType.DEPTH_ESTIMATION: self._depth_estimation,
            ModelTaskType.SPEECH_SEQ2SEQ: self._speech_seq2seq,
            ModelTaskType.CTC: self._ctc,
            ModelTaskType.AUDIO_CLASSIFICATION: self._audio_cls,
            ModelTaskType.VISION2SEQ: self._vision2seq,
            ModelTaskType.VISUAL_QA: self._visual_qa,
            ModelTaskType.DOCUMENT_QA: self._document_qa,
            ModelTaskType.TEXT_ENCODING: self._text_encoding,
            ModelTaskType.NEXT_SENTENCE: self._next_sentence,
            ModelTaskType.IMAGE_TO_IMAGE: self._image_to_image,
            ModelTaskType.TEXT_TO_WAVEFORM: self._text_to_waveform,
        }
        
        handler = handlers.get(task_type, self._fallback)
        return handler
    
    # ─── CAUSAL LM (Chat / Text Generation) ──────────────
    
    @torch.inference_mode()
    def _causal_lm(
        self, req: InferenceRequest
    ) -> tuple[dict, Optional[int]]:
        """Text generation / chat."""
        model = self.loader.model
        tokenizer = self.loader.tokenizer
        device = self.loader.model.device
        
        if not req.input_text:
            raise ValueError("input_text required for causal LM")
        
        # Try chat template first
        try:
            messages = [{"role": "user", "content": req.input_text}]
            input_text = tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
        except Exception:
            input_text = req.input_text
        
        inputs = tokenizer(
            input_text, 
            return_tensors="pt",
            truncation=True,
            max_length=2048,
        ).to(device)
        
        input_length = inputs["input_ids"].shape[1]
        
        outputs = model.generate(
            **inputs,
            max_new_tokens=req.max_new_tokens,
            temperature=max(req.temperature, 0.01),
            top_p=req.top_p,
            top_k=req.top_k,
            do_sample=req.do_sample,
            repetition_penalty=req.repetition_penalty,
            pad_token_id=tokenizer.pad_token_id,
        )
        
        generated_ids = outputs[0][input_length:]
        generated_text = tokenizer.decode(
            generated_ids, skip_special_tokens=True
        )
        tokens_generated = len(generated_ids)
        
        return {
            "generated_text": generated_text,
            "tokens_generated": tokens_generated,
        }, tokens_generated
    
    # ─── MASKED LM ───────────────────────────────────────
    
    @torch.inference_mode()
    def _masked_lm(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Fill-mask prediction."""
        model = self.loader.model
        tokenizer = self.loader.tokenizer
        device = model.device
        
        if not req.input_text:
            raise ValueError("input_text required")
        
        text = req.input_text
        if "[MASK]" not in text and "<mask>" not in text:
            text += " [MASK]"
        
        inputs = tokenizer(text, return_tensors="pt").to(device)
        outputs = model(**inputs)
        logits = outputs.logits
        
        # Find mask positions
        mask_token_id = tokenizer.mask_token_id
        mask_positions = (
            inputs["input_ids"] == mask_token_id
        ).nonzero(as_tuple=True)
        
        predictions = []
        for pos in mask_positions[1]:
            top_k = torch.topk(logits[0, pos], k=5)
            for score, idx in zip(
                top_k.values, top_k.indices
            ):
                token = tokenizer.decode([idx])
                predictions.append({
                    "token": token.strip(),
                    "score": round(score.item(), 4),
                })
        
        return {"predictions": predictions}, None
    
    # ─── SEQ2SEQ LM ──────────────────────────────────────
    
    @torch.inference_mode()
    def _seq2seq_lm(
        self, req: InferenceRequest
    ) -> tuple[dict, Optional[int]]:
        """Text-to-text generation."""
        model = self.loader.model
        tokenizer = self.loader.tokenizer
        device = model.device
        
        if not req.input_text:
            raise ValueError("input_text required")
        
        inputs = tokenizer(
            req.input_text, 
            return_tensors="pt",
            truncation=True,
            max_length=1024,
        ).to(device)
        
        outputs = model.generate(
            **inputs,
            max_new_tokens=req.max_new_tokens,
            temperature=max(req.temperature, 0.01),
            do_sample=req.do_sample,
        )
        
        generated_text = tokenizer.decode(
            outputs[0], skip_special_tokens=True
        )
        tokens_generated = len(outputs[0])
        
        return {
            "generated_text": generated_text,
        }, tokens_generated
    
    # ─── SEQUENCE CLASSIFICATION ──────────────────────────
    
    @torch.inference_mode()
    def _seq_cls(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Text classification."""
        model = self.loader.model
        tokenizer = self.loader.tokenizer
        device = model.device
        
        if not req.input_text:
            raise ValueError("input_text required")
        
        inputs = tokenizer(
            req.input_text, 
            return_tensors="pt",
            truncation=True,
        ).to(device)
        
        outputs = model(**inputs)
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)[0]
        
        # Get labels
        id2label = getattr(
            model.config, "id2label", 
            {i: f"LABEL_{i}" for i in range(len(probs))}
        )
        
        results = []
        for idx, prob in enumerate(probs):
            label = id2label.get(idx, f"LABEL_{idx}")
            results.append({
                "label": label,
                "score": round(prob.item(), 4),
            })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return {"classifications": results}, None
    
    # ─── TOKEN CLASSIFICATION ─────────────────────────────
    
    @torch.inference_mode()
    def _token_cls(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """NER / Token classification."""
        model = self.loader.model
        tokenizer = self.loader.tokenizer
        device = model.device
        
        if not req.input_text:
            raise ValueError("input_text required")
        
        inputs = tokenizer(
            req.input_text, 
            return_tensors="pt",
            truncation=True,
        ).to(device)
        
        outputs = model(**inputs)
        logits = outputs.logits
        predictions = torch.argmax(logits, dim=-1)[0]
        
        tokens = tokenizer.convert_ids_to_tokens(
            inputs["input_ids"][0]
        )
        
        id2label = getattr(
            model.config, "id2label",
            {i: f"LABEL_{i}" for i in range(logits.shape[-1])}
        )
        
        entities = []
        for token, pred in zip(tokens, predictions):
            label = id2label.get(pred.item(), f"LABEL_{pred}")
            if label != "O":
                entities.append({
                    "token": token,
                    "label": label,
                })
        
        return {"entities": entities}, None
    
    # ─── QUESTION ANSWERING ──────────────────────────────
    
    @torch.inference_mode()
    def _qa(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Extractive QA."""
        model = self.loader.model
        tokenizer = self.loader.tokenizer
        device = model.device
        
        if not req.question or not req.context:
            raise ValueError(
                "question and context required for QA"
            )
        
        inputs = tokenizer(
            req.question,
            req.context,
            return_tensors="pt",
            truncation=True,
        ).to(device)
        
        outputs = model(**inputs)
        
        start_idx = torch.argmax(outputs.start_logits, dim=-1)
        end_idx = torch.argmax(outputs.end_logits, dim=-1)
        
        answer_ids = inputs["input_ids"][0][
            start_idx:end_idx + 1
        ]
        answer = tokenizer.decode(
            answer_ids, skip_special_tokens=True
        )
        
        score = (
            outputs.start_logits[0][start_idx].item() +
            outputs.end_logits[0][end_idx].item()
        ) / 2
        
        return {
            "answer": answer,
            "score": round(score, 4),
        }, None
    
    # ─── MULTIPLE CHOICE ─────────────────────────────────
    
    @torch.inference_mode()
    def _multiple_choice(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Multiple choice."""
        model = self.loader.model
        tokenizer = self.loader.tokenizer
        device = model.device
        
        if not req.input_text or not req.candidate_labels:
            raise ValueError(
                "input_text and candidate_labels required"
            )
        
        choices = req.candidate_labels
        encoded = []
        
        for choice in choices:
            enc = tokenizer(
                req.input_text,
                choice,
                return_tensors="pt",
                truncation=True,
                padding="max_length",
                max_length=256,
            )
            encoded.append(enc)
        
        input_ids = torch.stack(
            [e["input_ids"].squeeze() for e in encoded]
        ).unsqueeze(0).to(device)
        
        attention_mask = torch.stack(
            [e["attention_mask"].squeeze() for e in encoded]
        ).unsqueeze(0).to(device)
        
        outputs = model(
            input_ids=input_ids, 
            attention_mask=attention_mask
        )
        probs = torch.softmax(outputs.logits, dim=-1)[0]
        
        results = []
        for i, choice in enumerate(choices):
            results.append({
                "choice": choice,
                "score": round(probs[i].item(), 4),
            })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return {"choices": results}, None
    
    # ─── IMAGE CLASSIFICATION ────────────────────────────
    
    @torch.inference_mode()
    def _image_cls(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Image classification."""
        model = self.loader.model
        processor = (
            self.loader.processor or 
            self.loader.feature_extractor
        )
        device = model.device
        
        image = self._load_image(req)
        
        inputs = processor(
            images=image, return_tensors="pt"
        ).to(device)
        
        outputs = model(**inputs)
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)[0]
        
        top_k = torch.topk(probs, k=min(5, len(probs)))
        id2label = getattr(model.config, "id2label", {})
        
        results = []
        for score, idx in zip(top_k.values, top_k.indices):
            label = id2label.get(
                idx.item(), f"CLASS_{idx.item()}"
            )
            results.append({
                "label": label,
                "score": round(score.item(), 4),
            })
        
        return {"classifications": results}, None
    
    # ─── OBJECT DETECTION ────────────────────────────────
    
    @torch.inference_mode()
    def _object_detection(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Object detection."""
        model = self.loader.model
        processor = self.loader.processor
        device = model.device
        
        image = self._load_image(req)
        
        inputs = processor(
            images=image, return_tensors="pt"
        ).to(device)
        
        outputs = model(**inputs)
        
        target_sizes = torch.tensor(
            [image.size[::-1]]
        ).to(device)
        results = processor.post_process_object_detection(
            outputs, 
            target_sizes=target_sizes,
            threshold=0.5,
        )[0]
        
        detections = []
        for score, label, box in zip(
            results["scores"], 
            results["labels"], 
            results["boxes"]
        ):
            detections.append({
                "label": model.config.id2label.get(
                    label.item(), str(label.item())
                ),
                "score": round(score.item(), 4),
                "box": {
                    "x1": round(box[0].item(), 2),
                    "y1": round(box[1].item(), 2),
                    "x2": round(box[2].item(), 2),
                    "y2": round(box[3].item(), 2),
                },
            })
        
        return {"detections": detections}, None
    
    # ─── SEMANTIC SEGMENTATION ───────────────────────────
    
    @torch.inference_mode()
    def _semantic_seg(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Semantic segmentation."""
        model = self.loader.model
        processor = self.loader.processor
        device = model.device
        
        image = self._load_image(req)
        
        inputs = processor(
            images=image, return_tensors="pt"
        ).to(device)
        
        outputs = model(**inputs)
        seg_map = outputs.logits.argmax(dim=1)[0]
        
        unique_classes = seg_map.unique().tolist()
        id2label = getattr(model.config, "id2label", {})
        
        classes_found = [
            id2label.get(c, f"class_{c}") 
            for c in unique_classes
        ]
        
        return {
            "segmentation_classes": classes_found,
            "num_classes": len(unique_classes),
            "map_shape": list(seg_map.shape),
        }, None
    
    # ─── DEPTH ESTIMATION ────────────────────────────────
    
    @torch.inference_mode()
    def _depth_estimation(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Depth estimation."""
        model = self.loader.model
        processor = self.loader.processor
        device = model.device
        
        image = self._load_image(req)
        
        inputs = processor(
            images=image, return_tensors="pt"
        ).to(device)
        
        outputs = model(**inputs)
        depth = outputs.predicted_depth
        
        return {
            "depth_shape": list(depth.shape),
            "depth_min": round(depth.min().item(), 4),
            "depth_max": round(depth.max().item(), 4),
            "depth_mean": round(depth.mean().item(), 4),
        }, None
    
    # ─── SPEECH SEQ2SEQ ──────────────────────────────────
    
    @torch.inference_mode()
    def _speech_seq2seq(
        self, req: InferenceRequest
    ) -> tuple[dict, Optional[int]]:
        """Speech-to-text."""
        model = self.loader.model
        processor = self.loader.processor
        device = model.device
        
        if not req.audio_path:
            raise ValueError("audio_path required")
        
        import torchaudio
        waveform, sample_rate = torchaudio.load(
            req.audio_path
        )
        
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(
                sample_rate, 16000
            )
            waveform = resampler(waveform)
        
        inputs = processor(
            waveform.squeeze().numpy(),
            sampling_rate=16000,
            return_tensors="pt",
        ).to(device)
        
        generated_ids = model.generate(**inputs)
        transcription = processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]
        
        return {
            "transcription": transcription,
        }, len(generated_ids[0])
    
    # ─── CTC ─────────────────────────────────────────────
    
    @torch.inference_mode()
    def _ctc(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """CTC-based speech recognition."""
        model = self.loader.model
        processor = (
            self.loader.processor or 
            self.loader.feature_extractor
        )
        tokenizer = self.loader.tokenizer
        device = model.device
        
        if not req.audio_path:
            raise ValueError("audio_path required")
        
        import torchaudio
        waveform, sample_rate = torchaudio.load(
            req.audio_path
        )
        
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(
                sample_rate, 16000
            )
            waveform = resampler(waveform)
        
        inputs = processor(
            waveform.squeeze().numpy(),
            sampling_rate=16000,
            return_tensors="pt",
        ).to(device)
        
        outputs = model(**inputs)
        logits = outputs.logits
        predicted_ids = torch.argmax(logits, dim=-1)
        
        if tokenizer:
            transcription = tokenizer.decode(
                predicted_ids[0]
            )
        else:
            transcription = processor.decode(
                predicted_ids[0]
            )
        
        return {"transcription": transcription}, None
    
    # ─── AUDIO CLASSIFICATION ────────────────────────────
    
    @torch.inference_mode()
    def _audio_cls(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Audio classification."""
        model = self.loader.model
        feature_extractor = (
            self.loader.feature_extractor or 
            self.loader.processor
        )
        device = model.device
        
        if not req.audio_path:
            raise ValueError("audio_path required")
        
        import torchaudio
        waveform, sample_rate = torchaudio.load(
            req.audio_path
        )
        
        inputs = feature_extractor(
            waveform.squeeze().numpy(),
            sampling_rate=sample_rate,
            return_tensors="pt",
        ).to(device)
        
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0]
        
        top_k = torch.topk(probs, k=min(5, len(probs)))
        id2label = getattr(model.config, "id2label", {})
        
        results = []
        for score, idx in zip(top_k.values, top_k.indices):
            results.append({
                "label": id2label.get(
                    idx.item(), f"CLASS_{idx.item()}"
                ),
                "score": round(score.item(), 4),
            })
        
        return {"classifications": results}, None
    
    # ─── VISION2SEQ (Image Captioning) ───────────────────
    
    @torch.inference_mode()
    def _vision2seq(
        self, req: InferenceRequest
    ) -> tuple[dict, Optional[int]]:
        """Image captioning / vision-to-text."""
        model = self.loader.model
        processor = self.loader.processor
        device = model.device
        
        image = self._load_image(req)
        
        text_input = req.input_text or ""
        
        inputs = processor(
            images=image,
            text=text_input if text_input else None,
            return_tensors="pt",
        ).to(device)
        
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=req.max_new_tokens,
        )
        
        caption = processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]
        
        return {
            "generated_text": caption,
        }, len(generated_ids[0])
    
    # ─── VISUAL QA ───────────────────────────────────────
    
    @torch.inference_mode()
    def _visual_qa(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Visual question answering."""
        model = self.loader.model
        processor = self.loader.processor
        device = model.device
        
        image = self._load_image(req)
        
        question = req.question or req.input_text
        if not question:
            raise ValueError(
                "question or input_text required"
            )
        
        inputs = processor(
            images=image,
            text=question,
            return_tensors="pt",
        ).to(device)
        
        outputs = model(**inputs)
        
        if hasattr(outputs, "logits"):
            probs = torch.softmax(outputs.logits, dim=-1)[0]
            top_k = torch.topk(probs, k=min(5, len(probs)))
            id2label = getattr(model.config, "id2label", {})
            
            answers = []
            for score, idx in zip(
                top_k.values, top_k.indices
            ):
                answers.append({
                    "answer": id2label.get(
                        idx.item(), str(idx.item())
                    ),
                    "score": round(score.item(), 4),
                })
            return {"answers": answers}, None
        
        # Generative VQA
        generated_ids = model.generate(
            **inputs, max_new_tokens=req.max_new_tokens
        )
        answer = processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]
        return {"answer": answer}, len(generated_ids[0])
    
    # ─── DOCUMENT QA ─────────────────────────────────────
    
    @torch.inference_mode()
    def _document_qa(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Document question answering."""
        model = self.loader.model
        processor = self.loader.processor
        device = model.device
        
        image = self._load_image(req)
        question = req.question or req.input_text
        
        if not question:
            raise ValueError("question required")
        
        inputs = processor(
            images=image,
            questions=[question],
            return_tensors="pt",
        ).to(device)
        
        outputs = model(**inputs)
        
        if hasattr(outputs, "start_logits"):
            start_idx = torch.argmax(outputs.start_logits)
            end_idx = torch.argmax(outputs.end_logits)
            answer = processor.tokenizer.decode(
                inputs["input_ids"][0][start_idx:end_idx + 1]
            )
            return {"answer": answer}, None
        
        return {"answer": "Unsupported output format"}, None
    
    # ─── TEXT ENCODING ───────────────────────────────────
    
    @torch.inference_mode()
    def _text_encoding(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Feature extraction / embeddings."""
        model = self.loader.model
        tokenizer = self.loader.tokenizer
        device = model.device
        
        texts = req.input_texts or (
            [req.input_text] if req.input_text else None
        )
        if not texts:
            raise ValueError("input_text(s) required")
        
        inputs = tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            padding=True,
        ).to(device)
        
        outputs = model(**inputs)
        
        # Mean pooling
        hidden = outputs.last_hidden_state
        mask = inputs["attention_mask"].unsqueeze(-1)
        embeddings = (hidden * mask).sum(1) / mask.sum(1)
        
        return {
            "embeddings": embeddings.cpu().tolist(),
            "dimensions": embeddings.shape[-1],
        }, None
    
    # ─── NEXT SENTENCE PREDICTION ────────────────────────
    
    @torch.inference_mode()
    def _next_sentence(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Next sentence prediction."""
        model = self.loader.model
        tokenizer = self.loader.tokenizer
        device = model.device
        
        if not req.input_text or not req.context:
            raise ValueError(
                "input_text (sentence A) and context "
                "(sentence B) required"
            )
        
        inputs = tokenizer(
            req.input_text,
            req.context,
            return_tensors="pt",
        ).to(device)
        
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0]
        
        return {
            "is_next": probs[0].item() > probs[1].item(),
            "next_prob": round(probs[0].item(), 4),
            "not_next_prob": round(probs[1].item(), 4),
        }, None
    
    # ─── IMAGE TO IMAGE ──────────────────────────────────
    
    @torch.inference_mode()
    def _image_to_image(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Image transformation."""
        model = self.loader.model
        processor = self.loader.processor
        device = model.device
        
        image = self._load_image(req)
        
        inputs = processor(
            images=image, return_tensors="pt"
        ).to(device)
        
        outputs = model(**inputs)
        
        return {
            "status": "processed",
            "output_shape": str(
                outputs.reconstruction.shape 
                if hasattr(outputs, "reconstruction") 
                else "unknown"
            ),
        }, None
    
    # ─── TEXT TO WAVEFORM ────────────────────────────────
    
    @torch.inference_mode()
    def _text_to_waveform(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Text-to-speech."""
        model = self.loader.model
        processor = self.loader.processor
        device = model.device
        
        if not req.input_text:
            raise ValueError("input_text required for TTS")
        
        inputs = processor(
            text=req.input_text, return_tensors="pt"
        ).to(device)
        
        outputs = model(**inputs)
        
        waveform = (
            outputs.waveform 
            if hasattr(outputs, "waveform") 
            else outputs.audio
        )
        
        return {
            "status": "generated",
            "audio_length_samples": waveform.shape[-1],
            "sample_rate": getattr(
                model.config, "sampling_rate", 16000
            ),
        }, None
    
    # ─── FALLBACK ────────────────────────────────────────
    
    @torch.inference_mode()
    def _fallback(
        self, req: InferenceRequest
    ) -> tuple[dict, None]:
        """Fallback for unsupported task types."""
        model = self.loader.model
        tokenizer = self.loader.tokenizer
        
        if tokenizer and req.input_text:
            device = model.device
            inputs = tokenizer(
                req.input_text, return_tensors="pt"
            ).to(device)
            
            outputs = model(**inputs)
            
            output_keys = [
                k for k in dir(outputs) 
                if not k.startswith("_")
            ]
            
            return {
                "status": "completed",
                "output_keys": output_keys,
                "note": (
                    "Fallback handler used. "
                    "Raw model output available."
                ),
            }, None
        
        return {
            "error": "Cannot process request with "
                     "current model type",
        }, None
    
    # ─── HELPERS ─────────────────────────────────────────
    
    def _load_image(
        self, req: InferenceRequest
    ) -> Image.Image:
        """Load image from request."""
        if req.image_path:
            return Image.open(req.image_path).convert("RGB")
        
        if req.image_url:
            import requests
            response = requests.get(req.image_url, stream=True)
            return Image.open(
                BytesIO(response.content)
            ).convert("RGB")
        
        raise ValueError(
            "image_path or image_url required "
            "for vision tasks"
        )