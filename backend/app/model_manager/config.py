"""
Configuration for the model manager.
All paths, constants, limits defined here.
"""

import os
from pathlib import Path
from enum import Enum


# ─── Base Paths ───────────────────────────────────────────
BASE_DIR = Path(os.environ.get(
    "SOVEREIGN_BASE", 
    Path.home() / ".sovereign-ai"
))
MODELS_DIR = BASE_DIR / "models" / "installed"
CACHE_DIR = BASE_DIR / "models" / ".cache"
REGISTRY_DB = BASE_DIR / "models" / "registry.db"

# Create directories
MODELS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
REGISTRY_DB.parent.mkdir(parents=True, exist_ok=True)

# ─── Limits ───────────────────────────────────────────────
MAX_STORAGE_GB = int(os.environ.get("SOVEREIGN_MAX_STORAGE", 50))
MAX_RAM_PERCENT = float(os.environ.get("SOVEREIGN_MAX_RAM", 0.75))

# ─── Device Config ────────────────────────────────────────
DEFAULT_DEVICE = os.environ.get("SOVEREIGN_DEVICE", "auto")
# auto | cpu | cuda | mps


class ModelStatus(str, Enum):
    """Status of a model in the registry."""
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    READY = "ready"
    LOADED = "loaded"
    FAILED = "failed"
    REMOVING = "removing"


class ModelTaskType(str, Enum):
    """All supported HuggingFace AutoModel task types."""
    # Language Modeling
    CAUSAL_LM = "causal-lm"
    MASKED_LM = "masked-lm"
    SEQ2SEQ_LM = "seq2seq-lm"
    SPEECH_SEQ2SEQ = "speech-seq2seq"
    VISION2SEQ = "vision2seq"
    
    # Classification
    SEQUENCE_CLASSIFICATION = "sequence-classification"
    TOKEN_CLASSIFICATION = "token-classification"
    MULTIPLE_CHOICE = "multiple-choice"
    NEXT_SENTENCE = "next-sentence-prediction"
    IMAGE_CLASSIFICATION = "image-classification"
    AUDIO_CLASSIFICATION = "audio-classification"
    VIDEO_CLASSIFICATION = "video-classification"
    
    # Question Answering
    QUESTION_ANSWERING = "question-answering"
    TABLE_QA = "table-question-answering"
    DOCUMENT_QA = "document-question-answering"
    VISUAL_QA = "visual-question-answering"
    
    # Text Variants
    TEXT_ENCODING = "text-encoding"
    TEXT_TO_SPECTROGRAM = "text-to-spectrogram"
    TEXT_TO_WAVEFORM = "text-to-waveform"
    CTC = "ctc"
    
    # Vision
    OBJECT_DETECTION = "object-detection"
    ZERO_SHOT_OBJECT_DETECTION = "zero-shot-object-detection"
    IMAGE_SEGMENTATION = "image-segmentation"
    SEMANTIC_SEGMENTATION = "semantic-segmentation"
    INSTANCE_SEGMENTATION = "instance-segmentation"
    DEPTH_ESTIMATION = "depth-estimation"
    MASKED_IMAGE_MODELING = "masked-image-modeling"
    
    # Audio
    AUDIO_FRAME_CLASSIFICATION = "audio-frame-classification"
    AUDIO_XVECTOR = "audio-xvector"
    
    # Multimodal
    VISION_TEXT_DUAL_ENCODER = "vision-text-dual-encoder"
    
    # Utility
    PRETRAINING = "pretraining"
    IMAGE_TO_IMAGE = "image-to-image"
    BACKBONE = "backbone"
    
    # Fallback
    UNKNOWN = "unknown"


# ─── Architecture → Task Mapping ──────────────────────────
# Maps known HuggingFace architecture suffixes to task types
ARCHITECTURE_TASK_MAP: dict[str, ModelTaskType] = {
    # Causal LM
    "ForCausalLM": ModelTaskType.CAUSAL_LM,
    "LMHeadModel": ModelTaskType.CAUSAL_LM,
    "GPT2LMHeadModel": ModelTaskType.CAUSAL_LM,
    "GPTNeoForCausalLM": ModelTaskType.CAUSAL_LM,
    "GPTNeoXForCausalLM": ModelTaskType.CAUSAL_LM,
    "GPTJForCausalLM": ModelTaskType.CAUSAL_LM,
    "LlamaForCausalLM": ModelTaskType.CAUSAL_LM,
    "MistralForCausalLM": ModelTaskType.CAUSAL_LM,
    "Qwen2ForCausalLM": ModelTaskType.CAUSAL_LM,
    "PhiForCausalLM": ModelTaskType.CAUSAL_LM,
    "Phi3ForCausalLM": ModelTaskType.CAUSAL_LM,
    "GemmaForCausalLM": ModelTaskType.CAUSAL_LM,
    "Gemma2ForCausalLM": ModelTaskType.CAUSAL_LM,
    "StableLmForCausalLM": ModelTaskType.CAUSAL_LM,
    "FalconForCausalLM": ModelTaskType.CAUSAL_LM,
    "CohereForCausalLM": ModelTaskType.CAUSAL_LM,
    "OPTForCausalLM": ModelTaskType.CAUSAL_LM,
    "BloomForCausalLM": ModelTaskType.CAUSAL_LM,
    
    # Masked LM
    "ForMaskedLM": ModelTaskType.MASKED_LM,
    "BertForMaskedLM": ModelTaskType.MASKED_LM,
    "RobertaForMaskedLM": ModelTaskType.MASKED_LM,
    "AlbertForMaskedLM": ModelTaskType.MASKED_LM,
    "DebertaForMaskedLM": ModelTaskType.MASKED_LM,
    "DebertaV2ForMaskedLM": ModelTaskType.MASKED_LM,
    
    # Seq2Seq
    "ForConditionalGeneration": ModelTaskType.SEQ2SEQ_LM,
    "T5ForConditionalGeneration": ModelTaskType.SEQ2SEQ_LM,
    "BartForConditionalGeneration": ModelTaskType.SEQ2SEQ_LM,
    "MarianMTModel": ModelTaskType.SEQ2SEQ_LM,
    "PegasusForConditionalGeneration": ModelTaskType.SEQ2SEQ_LM,
    
    # Sequence Classification
    "ForSequenceClassification": ModelTaskType.SEQUENCE_CLASSIFICATION,
    "BertForSequenceClassification": ModelTaskType.SEQUENCE_CLASSIFICATION,
    "RobertaForSequenceClassification": ModelTaskType.SEQUENCE_CLASSIFICATION,
    
    # Token Classification
    "ForTokenClassification": ModelTaskType.TOKEN_CLASSIFICATION,
    "BertForTokenClassification": ModelTaskType.TOKEN_CLASSIFICATION,
    
    # Question Answering
    "ForQuestionAnswering": ModelTaskType.QUESTION_ANSWERING,
    "BertForQuestionAnswering": ModelTaskType.QUESTION_ANSWERING,
    
    # Image Classification
    "ForImageClassification": ModelTaskType.IMAGE_CLASSIFICATION,
    "ViTForImageClassification": ModelTaskType.IMAGE_CLASSIFICATION,
    "SwinForImageClassification": ModelTaskType.IMAGE_CLASSIFICATION,
    
    # Object Detection
    "ForObjectDetection": ModelTaskType.OBJECT_DETECTION,
    "DetrForObjectDetection": ModelTaskType.OBJECT_DETECTION,
    "YolosForObjectDetection": ModelTaskType.OBJECT_DETECTION,
    
    # Segmentation
    "ForSemanticSegmentation": ModelTaskType.SEMANTIC_SEGMENTATION,
    "ForInstanceSegmentation": ModelTaskType.INSTANCE_SEGMENTATION,
    
    # Depth
    "ForDepthEstimation": ModelTaskType.DEPTH_ESTIMATION,
    "DPTForDepthEstimation": ModelTaskType.DEPTH_ESTIMATION,
    
    # Audio
    "ForCTC": ModelTaskType.CTC,
    "Wav2Vec2ForCTC": ModelTaskType.CTC,
    "HubertForCTC": ModelTaskType.CTC,
    "ForAudioClassification": ModelTaskType.AUDIO_CLASSIFICATION,
    "Wav2Vec2ForSequenceClassification": ModelTaskType.AUDIO_CLASSIFICATION,
    "WhisperForConditionalGeneration": ModelTaskType.SPEECH_SEQ2SEQ,
    
    # Speech Seq2Seq
    "ForSpeechSeq2Seq": ModelTaskType.SPEECH_SEQ2SEQ,
    
    # Vision2Seq
    "ForVision2Seq": ModelTaskType.VISION2SEQ,
    "VisionEncoderDecoderModel": ModelTaskType.VISION2SEQ,
    "Blip2ForConditionalGeneration": ModelTaskType.VISION2SEQ,
    "LlavaForConditionalGeneration": ModelTaskType.VISION2SEQ,
    
    # Multiple Choice
    "ForMultipleChoice": ModelTaskType.MULTIPLE_CHOICE,
    "BertForMultipleChoice": ModelTaskType.MULTIPLE_CHOICE,
    
    # Next Sentence
    "ForNextSentencePrediction": ModelTaskType.NEXT_SENTENCE,
    "BertForNextSentencePrediction": ModelTaskType.NEXT_SENTENCE,
    
    # Pretraining
    "ForPreTraining": ModelTaskType.PRETRAINING,
    "BertForPreTraining": ModelTaskType.PRETRAINING,
    
    # Image to Image
    "ForImageToImage": ModelTaskType.IMAGE_TO_IMAGE,
    
    # Backbone
    "Backbone": ModelTaskType.BACKBONE,
}

# ─── Pipeline Tag → Task Mapping ─────────────────────────
PIPELINE_TASK_MAP: dict[str, ModelTaskType] = {
    "text-generation": ModelTaskType.CAUSAL_LM,
    "text2text-generation": ModelTaskType.SEQ2SEQ_LM,
    "fill-mask": ModelTaskType.MASKED_LM,
    "text-classification": ModelTaskType.SEQUENCE_CLASSIFICATION,
    "sentiment-analysis": ModelTaskType.SEQUENCE_CLASSIFICATION,
    "token-classification": ModelTaskType.TOKEN_CLASSIFICATION,
    "ner": ModelTaskType.TOKEN_CLASSIFICATION,
    "question-answering": ModelTaskType.QUESTION_ANSWERING,
    "table-question-answering": ModelTaskType.TABLE_QA,
    "document-question-answering": ModelTaskType.DOCUMENT_QA,
    "visual-question-answering": ModelTaskType.VISUAL_QA,
    "summarization": ModelTaskType.SEQ2SEQ_LM,
    "translation": ModelTaskType.SEQ2SEQ_LM,
    "conversational": ModelTaskType.CAUSAL_LM,
    "image-classification": ModelTaskType.IMAGE_CLASSIFICATION,
    "object-detection": ModelTaskType.OBJECT_DETECTION,
    "zero-shot-object-detection": ModelTaskType.ZERO_SHOT_OBJECT_DETECTION,
    "image-segmentation": ModelTaskType.IMAGE_SEGMENTATION,
    "semantic-segmentation": ModelTaskType.SEMANTIC_SEGMENTATION,
    "depth-estimation": ModelTaskType.DEPTH_ESTIMATION,
    "image-to-image": ModelTaskType.IMAGE_TO_IMAGE,
    "automatic-speech-recognition": ModelTaskType.SPEECH_SEQ2SEQ,
    "audio-classification": ModelTaskType.AUDIO_CLASSIFICATION,
    "text-to-speech": ModelTaskType.TEXT_TO_WAVEFORM,
    "text-to-audio": ModelTaskType.TEXT_TO_WAVEFORM,
    "video-classification": ModelTaskType.VIDEO_CLASSIFICATION,
    "feature-extraction": ModelTaskType.TEXT_ENCODING,
    "image-feature-extraction": ModelTaskType.BACKBONE,
    "multiple-choice": ModelTaskType.MULTIPLE_CHOICE,
}