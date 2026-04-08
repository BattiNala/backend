import json

from app.services.issue_image_validation_service import IssueImageValidationService


def test_orb_similarity():
    image1 = "tests/cli_tests/STEP_1.png"
    image2 = "tests/cli_tests/STEP_2.png"
    result = IssueImageValidationService.compute_orb_similarity(image1, image2)
    assert isinstance(result, dict)
    assert "good_matches" in result
    assert "total_matches" in result
    assert "similarity_score" in result
    print(f"ORB Similarity Result: {json.dumps(result, indent=2)}")


test_orb_similarity()
