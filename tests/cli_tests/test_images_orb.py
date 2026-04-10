"""CLI smoke test for pHash and ORB image similarity."""

import json
import sys
from numbers import Integral
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.issue_image_validation_service import IssueImageValidationService

DEFAULT_IMAGE_1 = Path("tests/cli_tests/pole_1.jpg")
DEFAULT_IMAGE_2 = Path("tests/cli_tests/pole_2.jpg")


def _resolve_image_paths() -> tuple[Path, Path]:
    """Return two image paths from CLI args or bundled defaults."""
    args = sys.argv[1:]
    if len(args) == 2:
        return Path(args[0]), Path(args[1])
    if not args:
        return DEFAULT_IMAGE_1, DEFAULT_IMAGE_2
    raise RuntimeError("Usage: python tests/cli_tests/test_images_orb.py [image1 image2]")


def run_image_similarity_smoke_test() -> None:
    """Compute pHash and ORB metrics for two local images."""
    image1, image2 = _resolve_image_paths()

    for image_path in (image1, image2):
        if not image_path.is_file():
            raise RuntimeError(f"Image file not found: {image_path}")

    phash_1 = IssueImageValidationService.compute_phash(str(image1))
    phash_2 = IssueImageValidationService.compute_phash(str(image2))
    phash_distance = IssueImageValidationService.phash_distance(phash_1, phash_2)
    orb_result = IssueImageValidationService.compute_orb_similarity(str(image1), str(image2))

    assert phash_1 is not None
    assert phash_2 is not None
    assert isinstance(phash_distance, Integral)
    assert isinstance(orb_result, dict)
    assert "good_matches" in orb_result
    assert "total_matches" in orb_result
    assert "similarity_score" in orb_result

    result = {
        "image_1": str(image1),
        "image_2": str(image2),
        "phash_1": phash_1,
        "phash_2": phash_2,
        "phash_distance": int(phash_distance),
        "orb_similarity": {
            "good_matches": int(orb_result["good_matches"]),
            "total_matches": int(orb_result["total_matches"]),
            "similarity_score": float(orb_result["similarity_score"]),
        },
    }
    print(json.dumps(result, indent=2))


run_image_similarity_smoke_test()
