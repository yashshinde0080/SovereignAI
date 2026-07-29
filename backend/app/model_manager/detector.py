"""
Auto-detect model task type from HuggingFace model config.
Inspects config.json architectures, pipeline tags, model card.
"""

import json
import logging
from pathlib import Path
from typing import Optional
from huggingface_hub import model_info as hf_model_info

from .config import (
    ModelTaskType,
    ARCHITECTURE_TASK_MAP,
    PIPELINE_TASK_MAP,
)

logger = logging.getLogger("sovereign.detector")


class ModelDetector:
    """
    Detects the appropriate AutoModel class for a HuggingFace model.
    
    Detection priority:
    1. User override (if provided)
    2. Architecture from config.json
    3. Pipeline tag from HuggingFace API
    4. Fallback to CAUSAL_LM (most common)
    """
    
    @staticmethod
    def detect_from_repo(
        repo_id: str,
        revision: Optional[str] = None,
        override: Optional[ModelTaskType] = None,
    ) -> tuple[ModelTaskType, Optional[list[str]]]:
        """
        Detect task type from HuggingFace repo.
        
        Returns:
            (task_type, architectures_list)
        """
        if override and override != ModelTaskType.UNKNOWN:
            logger.info(
                f"Using user override task type: {override.value}"
            )
            return override, None
        
        architectures = None
        
        # Strategy 1: Get model info from HuggingFace API
        try:
            info = hf_model_info(repo_id, revision=revision)
            
            # Check pipeline tag
            if info.pipeline_tag:
                tag = info.pipeline_tag
                if tag in PIPELINE_TASK_MAP:
                    logger.info(
                        f"Detected task from pipeline tag: "
                        f"{tag} → {PIPELINE_TASK_MAP[tag].value}"
                    )
                    
                    # Also try to get architectures
                    if hasattr(info, 'config') and info.config:
                        arch = info.config.get('architectures', [])
                        if arch:
                            architectures = arch
                    
                    return PIPELINE_TASK_MAP[tag], architectures
            
            # Check config architectures
            if hasattr(info, 'config') and info.config:
                arch_list = info.config.get('architectures', [])
                if arch_list:
                    architectures = arch_list
                    detected = ModelDetector._match_architecture(
                        arch_list
                    )
                    if detected != ModelTaskType.UNKNOWN:
                        return detected, architectures
            
            # Check tags
            if info.tags:
                for tag in info.tags:
                    if tag in PIPELINE_TASK_MAP:
                        return PIPELINE_TASK_MAP[tag], architectures
        
        except Exception as e:
            logger.warning(
                f"Could not fetch model info from HF API: {e}"
            )
        
        logger.warning(
            f"Could not auto-detect task type for {repo_id}. "
            f"Defaulting to causal-lm."
        )
        return ModelTaskType.CAUSAL_LM, architectures
    
    @staticmethod
    def detect_from_local(
        model_path: Path,
        override: Optional[ModelTaskType] = None,
    ) -> tuple[ModelTaskType, Optional[list[str]]]:
        """
        Detect task type from local model directory.
        Reads config.json.
        """
        if override and override != ModelTaskType.UNKNOWN:
            return override, None
        
        config_path = model_path / "config.json"
        architectures = None
        
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                
                arch_list = config.get("architectures", [])
                if arch_list:
                    architectures = arch_list
                    detected = ModelDetector._match_architecture(
                        arch_list
                    )
                    if detected != ModelTaskType.UNKNOWN:
                        return detected, architectures
                
                # Check model_type field
                model_type = config.get("model_type", "")
                if model_type:
                    detected = ModelDetector._match_model_type(
                        model_type
                    )
                    if detected != ModelTaskType.UNKNOWN:
                        return detected, architectures
                        
            except Exception as e:
                logger.warning(
                    f"Error reading config.json: {e}"
                )
        
        return ModelTaskType.CAUSAL_LM, architectures
    
    @staticmethod
    def _match_architecture(
        architectures: list[str]
    ) -> ModelTaskType:
        """Match architecture names to task types."""
        for arch in architectures:
            # Direct match
            if arch in ARCHITECTURE_TASK_MAP:
                return ARCHITECTURE_TASK_MAP[arch]
            
            # Suffix match
            for suffix, task in ARCHITECTURE_TASK_MAP.items():
                if arch.endswith(suffix):
                    return task
        
        return ModelTaskType.UNKNOWN
    
    @staticmethod
    def _match_model_type(model_type: str) -> ModelTaskType:
        """
        Fallback: guess from model_type field.
        This is less reliable.
        """
        generative_types = {
            "llama", "mistral", "gpt2", "gpt_neo", "gpt_neox",
            "gptj", "phi", "phi3", "gemma", "gemma2", "gemma3",
            "gemma4", "falcon", "bloom", "opt", "qwen2", "qwen3",
            "qwen2_moe", "qwen2_5", "cohere", "stablelm",
            "starcoder2", "codellama", "deepseek", "deepseek_v2",
            "deepseek_v3", "deepseek_v4", "dbrx", "jamba",
            "exaone4", "exaone_moe", "olmo", "olmo2", "olmo3",
            "bitnet", "mpt", "mamba", "mamba2", "mixtral",
            "ministral", "granite", "granitemoe", "nemotron",
            "persimmon", "recurrent_gemma", "jetmoe", "bamba",
            "minicpm3", "glm", "glm4", "zamba", "zamba2",
            "internlm2", "xglm", "rwkv", "biogpt", "git",
            "codegen", "gpt_bigcode", "gpt_neox_japanese",
            "nanochat", "solar_open", "arcee", "apertus",
            "smollm3", "helium", "diffllama", "blt",
        }
        
        encoder_types = {
            "bert", "roberta", "albert", "deberta", "electra",
            "distilbert", "xlm-roberta", "modernbert", "canine",
            "camembert", "flaubert", "layoutlm", "longformer",
            "luke", "mpnet", "nomic_bert", "rembert", "splinter",
            "squeezebert", "xlm", "xmod", "yoso", "ernie",
            "mobilebert", "big_bird", "funnel", "ibert",
            "megatron-bert", "nystromformer", "reformer",
            "roformer", "data2vec-text",
        }
        
        seq2seq_types = {
            "t5", "bart", "mbart", "pegasus", "marian", "mt5",
            "flan-t5", "longt5", "m2m_100", "bigbird_pegasus",
            "blenderbot", "fsmt", "led", "mvp", "nllb-moe",
            "plbart", "prophetnet", "seamless_m4t", "speech_to_text",
            "speecht5", "switch_transformers", "umt5", "whisper",
        }
        
        vision_types = {
            "vit", "swin", "deit", "beit", "convnext",
            "resnet", "efficientnet", "convnextv2", "dinov2",
            "bit", "cvt", "focalnet", "imagegpt", "levit",
            "mobilevit", "mobilevitv2", "nat", "poolformer",
            "pvt", "regnet", "segformer", "swinv2",
            "timesformer", "vit_mae", "vit_msn", "yolos",
            "dinat", "hiera", "maskformer", "depth_pro",
        }
        
        mt = model_type.lower().replace("-", "_")
        
        if mt in generative_types:
            return ModelTaskType.CAUSAL_LM
        if mt in encoder_types:
            return ModelTaskType.MASKED_LM
        if mt in seq2seq_types:
            return ModelTaskType.SEQ2SEQ_LM
        if mt in vision_types:
            return ModelTaskType.IMAGE_CLASSIFICATION
        
        return ModelTaskType.UNKNOWN
    
    @staticmethod
    def get_auto_class_name(task_type: ModelTaskType) -> str:
        """
        Get the transformers AutoModel class name for a task.
        """
        mapping = {
            ModelTaskType.CAUSAL_LM: "AutoModelForCausalLM",
            ModelTaskType.MASKED_LM: "AutoModelForMaskedLM",
            ModelTaskType.SEQ2SEQ_LM: "AutoModelForSeq2SeqLM",
            ModelTaskType.SPEECH_SEQ2SEQ: "AutoModelForSpeechSeq2Seq",
            ModelTaskType.VISION2SEQ: "AutoModelForVision2Seq",
            ModelTaskType.SEQUENCE_CLASSIFICATION: "AutoModelForSequenceClassification",
            ModelTaskType.TOKEN_CLASSIFICATION: "AutoModelForTokenClassification",
            ModelTaskType.MULTIPLE_CHOICE: "AutoModelForMultipleChoice",
            ModelTaskType.NEXT_SENTENCE: "AutoModelForNextSentencePrediction",
            ModelTaskType.IMAGE_CLASSIFICATION: "AutoModelForImageClassification",
            ModelTaskType.AUDIO_CLASSIFICATION: "AutoModelForAudioClassification",
            ModelTaskType.VIDEO_CLASSIFICATION: "AutoModelForVideoClassification",
            ModelTaskType.QUESTION_ANSWERING: "AutoModelForQuestionAnswering",
            ModelTaskType.TABLE_QA: "AutoModelForTableQuestionAnswering",
            ModelTaskType.DOCUMENT_QA: "AutoModelForDocumentQuestionAnswering",
            ModelTaskType.VISUAL_QA: "AutoModelForVisualQuestionAnswering",
            ModelTaskType.TEXT_ENCODING: "AutoModel",
            ModelTaskType.TEXT_TO_SPECTROGRAM: "AutoModelForTextToSpectrogram",
            ModelTaskType.TEXT_TO_WAVEFORM: "AutoModelForTextToWaveform",
            ModelTaskType.CTC: "AutoModelForCTC",
            ModelTaskType.OBJECT_DETECTION: "AutoModelForObjectDetection",
            ModelTaskType.ZERO_SHOT_OBJECT_DETECTION: "AutoModelForZeroShotObjectDetection",
            ModelTaskType.IMAGE_SEGMENTATION: "AutoModelForImageSegmentation",
            ModelTaskType.SEMANTIC_SEGMENTATION: "AutoModelForSemanticSegmentation",
            ModelTaskType.INSTANCE_SEGMENTATION: "AutoModelForInstanceSegmentation",
            ModelTaskType.DEPTH_ESTIMATION: "AutoModelForDepthEstimation",
            ModelTaskType.MASKED_IMAGE_MODELING: "AutoModelForMaskedImageModeling",
            ModelTaskType.AUDIO_FRAME_CLASSIFICATION: "AutoModelForAudioFrameClassification",
            ModelTaskType.AUDIO_XVECTOR: "AutoModelForAudioXVector",
            ModelTaskType.VISION_TEXT_DUAL_ENCODER: "VisionTextDualEncoderModel",
            ModelTaskType.PRETRAINING: "AutoModelForPreTraining",
            ModelTaskType.IMAGE_TO_IMAGE: "AutoModelForImageToImage",
            ModelTaskType.BACKBONE: "AutoBackbone",
            ModelTaskType.UNKNOWN: "AutoModel",
        }
        return mapping.get(task_type, "AutoModel")