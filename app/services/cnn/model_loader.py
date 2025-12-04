import torch
from torchvision.models import mobilenet_v3_large, MobileNet_V3_Large_Weights
from torchvision import transforms

# 모델과 전처리를 캐싱하여 매번 로드되지 않도록 함
_model = None
_preprocess = None
_EMB_SIZE = 960


def load_model():
    """
    MobileNetV3 Large 모델을 초기화하고 전처리(transform)를 설정한다.
    서비스 시작 시 1회만 실행되며, 이후에는 캐싱된 모델을 사용한다.

    기능:
    - ImageNet 사전학습 MobileNetV3 Large 로드
    - 분류기(Classifier)를 Identity()로 교체하여 960차원 feature embedding 추출
    - 모델을 eval() 모드로 설정 (inference 최적화)
    - 이미지 resize/normalize를 수행하는 preprocess 함수 생성

    Returns:
        tuple(model, preprocess, emb_size)
        model: torch.nn.Module (MobileNetV3 Large feature extractor)
        preprocess: callable - 이미지 텐서 변환 함수
        emb_size: int - 임베딩 차원(960)
    """

    global _model, _preprocess, _EMB_SIZE

    if _model is not None:
        # 이미 로드됨 → 재사용
        return _model, _preprocess, _EMB_SIZE

    print("[ModelLoader] MobileNetV3 Large 모델 로드 시작")

    # 1) 사전학습 가중치 로드
    weights = MobileNet_V3_Large_Weights.IMAGENET1K_V2
    model = mobilenet_v3_large(weights=weights)

    # 2) classifier 제거 → 960차원 embedding vector 출력
    model.classifier = torch.nn.Identity()

    # 3) evaluation mode
    model.eval()

    print("[ModelLoader] MobileNetV3 Large 로드 완료")
    print(f"[ModelLoader] Embedding dimension = {_EMB_SIZE}")

    # 4) 이미지 전처리 transform 정의
    preprocess = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    # 5) warm-up 실행 (성능 최적화)
    print("[ModelLoader] Warm-up 실행 중")
    with torch.no_grad():
        dummy = torch.zeros(1, 3, 224, 224)
        _ = model(dummy)

    print("[ModelLoader] Warm-up 완료")

    # 캐싱
    _model = model
    _preprocess = preprocess

    return _model, _preprocess, _EMB_SIZE


def get_model():
    """
    이미 로딩된 모델을 반환하거나,
    로드되지 않았다면 load_model()을 호출하여 자동 초기화한다.

    Returns:
        torch.nn.Module: MobileNetV3 Large embedding extractor
    """
    global _model

    if _model is None:
        load_model()

    return _model


def get_preprocess():
    """
    이미지 전처리(transform) 함수를 반환한다.
    모델과 함께 생성되며, load_model()이 자동으로 초기화한다.

    Returns:
        preprocess (callable): PIL Image → Tensor 변환 함수
    """
    global _preprocess

    if _preprocess is None:
        load_model()

    return _preprocess


def get_embedding_size():
    """
    MobileNetV3 Large에서 출력되는 embedding 차원을 반환한다.

    Returns:
        int: 960
    """
    return _EMB_SIZE