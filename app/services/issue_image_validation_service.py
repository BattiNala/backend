"""Validation service for issue image comparison and related checks."""

from __future__ import annotations

from typing import Sequence, TypedDict

import cv2  # pylint: disable=no-member
import imagehash
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps

from app.core.logger import get_logger

logger = get_logger("services.issue_image_validation_service")


class ORBSimilarityResult(TypedDict):  # pylint: disable=too-few-public-methods
    """Structured result for ORB-based image similarity."""

    good_matches: int
    total_matches: int
    similarity_score: float


class CosineSimilarityResult(TypedDict):  # pylint: disable=too-few-public-methods
    """Structured result for cosine-based image similarity."""

    similarity_score: float


class IssueImageValidationService:  # pylint: disable=too-few-public-methods
    """Service for validating issues using image similarity checks."""

    @staticmethod
    def compute_phash(image_path: str) -> str | None:
        """Compute the perceptual hash (pHash) of an image."""
        try:
            logger.debug("Computing pHash for image: %s", image_path)
            with Image.open(image_path) as img:
                img = ImageOps.exif_transpose(img)
                img = img.convert("RGB")
                phash = imagehash.phash(img)
            logger.debug("pHash for %s: %s", image_path, phash)
            return str(phash)
        except (OSError, ValueError, TypeError) as e:
            logger.error("Failed pHash computation for %s: %s", image_path, e)
            return None

    @staticmethod
    def phash_distance(hash1: str, hash2: str) -> int:
        """Compute the Hamming distance between two perceptual hashes."""
        logger.debug("Computing Hamming distance: hash1=%s, hash2=%s", hash1, hash2)
        if not hash1 or not hash2:
            logger.warning("One or both pHash values are missing; returning max distance (999)")
            return 999
        dist = imagehash.hex_to_hash(hash1) - imagehash.hex_to_hash(hash2)
        logger.debug("Computed Hamming distance: %s", dist)
        return dist

    @staticmethod
    def _empty_similarity_result() -> ORBSimilarityResult:
        """Return a default similarity result."""
        return {
            "good_matches": 0,
            "total_matches": 0,
            "similarity_score": 0.0,
        }

    @staticmethod
    def _empty_cosine_similarity_result() -> CosineSimilarityResult:
        """Return a default cosine similarity result."""
        return {
            "similarity_score": 0.0,
        }

    @staticmethod
    def _load_grayscale_image(image_path: str) -> NDArray[np.uint8] | None:
        """Load an image in grayscale mode."""
        logger.debug("Loading image in grayscale: %s", image_path)
        return cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    @staticmethod
    def _load_color_image(image_path: str) -> NDArray[np.uint8] | None:
        """Load an image in color mode."""
        logger.debug("Loading image in color: %s", image_path)
        return cv2.imread(image_path, cv2.IMREAD_COLOR)

    @staticmethod
    def compute_orb_similarity(
        image_path_1: str,
        image_path_2: str,
        max_features: int = 500,
        ratio_threshold: float = 0.75,
    ) -> ORBSimilarityResult:
        """Compute ORB feature similarity metrics between two images."""
        try:
            logger.debug("Computing ORB similarity: %s vs %s", image_path_1, image_path_2)
            img1 = IssueImageValidationService._load_grayscale_image(image_path_1)
            img2 = IssueImageValidationService._load_grayscale_image(image_path_2)

            if img1 is None or img2 is None:
                logger.warning(
                    "Could not load one or both images for ORB similarity; returning empty result"
                )
                return IssueImageValidationService._empty_similarity_result()

            result = IssueImageValidationService._match_orb_features(
                img1=img1,
                img2=img2,
                max_features=max_features,
                ratio_threshold=ratio_threshold,
            )
            logger.debug("ORB similarity result: %s", result)
            return result
        except (cv2.error, OSError, ValueError, TypeError) as e:
            logger.error("Error during ORB similarity computation: %s", e)
            return IssueImageValidationService._empty_similarity_result()

    @staticmethod
    def compute_cosine_similarity(
        image_path_1: str,
        image_path_2: str,
        hue_bins: int = 24,
        saturation_bins: int = 16,
    ) -> CosineSimilarityResult:
        """Compute cosine similarity between normalized HSV histograms."""
        try:
            logger.debug(
                "Computing cosine similarity on image histograms: %s vs %s",
                image_path_1,
                image_path_2,
            )
            img1 = IssueImageValidationService._load_color_image(image_path_1)
            img2 = IssueImageValidationService._load_color_image(image_path_2)

            if img1 is None or img2 is None:
                logger.warning(
                    "Could not load one or both images for cosine similarity; returning empty res"
                )
                return IssueImageValidationService._empty_cosine_similarity_result()

            result = IssueImageValidationService._compare_hsv_histograms(
                img1=img1,
                img2=img2,
                hue_bins=hue_bins,
                saturation_bins=saturation_bins,
            )
            logger.debug("Cosine similarity result: %s", result)
            return result
        except (cv2.error, OSError, ValueError, TypeError) as e:
            logger.error("Error during cosine similarity computation: %s", e)
            return IssueImageValidationService._empty_cosine_similarity_result()

    @staticmethod
    def compute_embedding_cosine_similarity(
        embedding_1: Sequence[float] | None,
        embedding_2: Sequence[float] | None,
    ) -> CosineSimilarityResult:
        """Compute cosine similarity between two embedding vectors."""
        try:
            logger.debug(
                "Computing embedding cosine similarity: embedding_1=%s, embedding_2=%s",
                embedding_1,
                embedding_2,
            )
            if embedding_1 is None or embedding_2 is None:
                logger.warning("One or both embeddings are missing; returning empty result")
                return IssueImageValidationService._empty_cosine_similarity_result()

            vector_1 = np.asarray(embedding_1, dtype=np.float32)
            vector_2 = np.asarray(embedding_2, dtype=np.float32)

            if vector_1.size == 0 or vector_2.size == 0 or vector_1.shape != vector_2.shape:
                logger.warning(
                    "Invalid embeddings (empty or mismatched shape); returning empty result"
                )
                return IssueImageValidationService._empty_cosine_similarity_result()

            norm_1 = float(np.linalg.norm(vector_1))
            norm_2 = float(np.linalg.norm(vector_2))
            if norm_1 == 0.0 or norm_2 == 0.0:
                logger.warning("Zero-norm embedding vector(s); returning empty result")
                return IssueImageValidationService._empty_cosine_similarity_result()

            similarity_score = float(np.dot(vector_1 / norm_1, vector_2 / norm_2))
            result = {
                "similarity_score": round(similarity_score, 4),
            }
            logger.debug("Embedding cosine similarity result: %s", result)
            return result
        except (ValueError, TypeError) as e:
            logger.error("Error during embedding cosine similarity computation: %s", e)
            return IssueImageValidationService._empty_cosine_similarity_result()

    @staticmethod
    def _match_orb_features(  # pylint: disable=too-many-locals
        img1: NDArray[np.uint8],
        img2: NDArray[np.uint8],
        max_features: int,
        ratio_threshold: float,
    ) -> ORBSimilarityResult:
        """Extract ORB features, match them, and compute similarity metrics."""
        logger.debug(
            "Matching ORB features: max_features=%s, ratio_threshold=%s, "
            "img1.shape=%s, img2.shape=%s",
            max_features,
            ratio_threshold,
            getattr(img1, "shape", None),
            getattr(img2, "shape", None),
        )
        orb = cv2.ORB_create(nfeatures=max_features)

        kp1, des1 = orb.detectAndCompute(img1, None)
        kp2, des2 = orb.detectAndCompute(img2, None)

        if des1 is None or des2 is None or len(kp1) == 0 or len(kp2) == 0:
            logger.warning(
                "No descriptors or keypoints found in one or both images;"
                " returning empty similarity result"
            )
            return IssueImageValidationService._empty_similarity_result()

        bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        knn_matches = bf_matcher.knnMatch(des1, des2, k=2)

        good_matches = [
            first
            for pair in knn_matches
            if len(pair) == 2
            for first, second in [pair]
            if first.distance < ratio_threshold * second.distance
        ]

        total_matches = len(knn_matches)
        min_keypoints = min(len(kp1), len(kp2))
        similarity_score = len(good_matches) / min_keypoints if min_keypoints > 0 else 0.0

        result = {
            "good_matches": len(good_matches),
            "total_matches": total_matches,
            "similarity_score": round(similarity_score, 4),
        }
        logger.debug("ORB match result: %s", result)
        return result

    @staticmethod
    def _compare_hsv_histograms(
        img1: NDArray[np.uint8],
        img2: NDArray[np.uint8],
        hue_bins: int,
        saturation_bins: int,
    ) -> CosineSimilarityResult:
        """Build normalized HSV histograms and compare them with cosine similarity."""
        logger.debug("Computing normalized HSV histograms for comparison")
        histogram_1 = IssueImageValidationService._normalized_hsv_histogram(
            img1,
            hue_bins=hue_bins,
            saturation_bins=saturation_bins,
        )
        histogram_2 = IssueImageValidationService._normalized_hsv_histogram(
            img2,
            hue_bins=hue_bins,
            saturation_bins=saturation_bins,
        )

        if histogram_1.size == 0 or histogram_2.size == 0:
            logger.warning(
                "One or both histograms are empty; returning empty cosine similarity result"
            )
            return IssueImageValidationService._empty_cosine_similarity_result()

        similarity_score = float(np.dot(histogram_1, histogram_2))
        result = {
            "similarity_score": round(similarity_score, 4),
        }
        logger.debug("HSV histogram cosine similarity result: %s", result)
        return result

    @staticmethod
    def _normalized_hsv_histogram(
        image: NDArray[np.uint8],
        hue_bins: int,
        saturation_bins: int,
    ) -> NDArray[np.float32]:
        """Return a unit-length HSV histogram for cosine comparison."""
        logger.debug(
            "Building HSV histogram: hue_bins=%s, saturation_bins=%s, image_shape=%s",
            hue_bins,
            saturation_bins,
            getattr(image, "shape", None),
        )
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        histogram = cv2.calcHist(
            [hsv_image],
            [0, 1],
            None,
            [hue_bins, saturation_bins],
            [0, 180, 0, 256],
        )

        flattened = histogram.astype(np.float32).reshape(-1)
        norm = np.linalg.norm(flattened)
        if norm == 0.0:
            logger.warning("HSV histogram norm is zero; returning empty array")
            return np.array([], dtype=np.float32)

        hist_norm = flattened / norm
        logger.info("Computed normalized HSV histogram (len=%s)", len(hist_norm))
        return hist_norm
