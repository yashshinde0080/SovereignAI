
import transformers
import inspect

requested = [
    "AutoModelForCausalLM", "AutoModelForMaskedLM", "AutoModelForSeq2SeqLM",
    "AutoModelForSpeechSeq2Seq", "AutoModelForVision2Seq",
    "AutoModelForSequenceClassification", "AutoModelForTokenClassification",
    "AutoModelForMultipleChoice", "AutoModelForNextSentencePrediction",
    "AutoModelForImageClassification", "AutoModelForAudioClassification",
    "AutoModelForVideoClassification", "AutoModelForQuestionAnswering",
    "AutoModelForTableQuestionAnswering", "AutoModelForDocumentQuestionAnswering",
    "AutoModelForVisualQuestionAnswering", "AutoModelForTextEncoding",
    "AutoModelForTextToSpectrogram", "AutoModelForTextToWaveform",
    "AutoModelForCTC", "AutoModelForObjectDetection",
    "AutoModelForZeroShotObjectDetection", "AutoModelForImageSegmentation",
    "AutoModelForSemanticSegmentation", "AutoModelForInstanceSegmentation",
    "AutoModelForDepthEstimation", "AutoModelForMaskedImageModeling",
    "AutoModelForAudioFrameClassification", "AutoModelForAudioXVector",
    "AutoModelForVisionTextDualEncoder", "AutoModelForPreTraining",
    "AutoModelForImageToImage", "AutoModelForBackbone"
]

found = []
missing = []

for name in requested:
    if hasattr(transformers, name):
        found.append(name)
    else:
        # Fallback for AutoModelForTextEncoding
        if name == "AutoModelForTextEncoding" and hasattr(transformers, "AutoModel"):
             found.append("AutoModel (as fallback for TextEncoding)")
        else:
             missing.append(name)

print(f"Found: {len(found)}")
for f in found:
    print(f"  [+] {f}")

print(f"Missing: {len(missing)}")
for m in missing:
    print(f"  [-] {m}")
