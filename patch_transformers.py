#!/usr/bin/env python3
"""
Patches transformers 5.x to add back the removed isin_mps_friendly function.
This function was removed in transformers 5.x but coqui-tts still imports it.
"""

import importlib
import sys


def patch_transformers():
    """Add isin_mps_friendly to transformers.pytorch_utils if missing."""
    try:
        from transformers.pytorch_utils import isin_mps_friendly
        return  # Already exists, no patch needed
    except ImportError:
        pass

    import torch
    import transformers.pytorch_utils as pu

    def isin_mps_friendly(elements, test_elements):
        """MPS-friendly version of torch.isin (workaround for MPS backend bugs)."""
        if elements.device.type == "mps" or (
            hasattr(test_elements, "device") and test_elements.device.type == "mps"
        ):
            return elements.unsqueeze(-1).eq(test_elements).any(-1)
        return torch.isin(elements, test_elements)

    # Inject the function into the module
    pu.isin_mps_friendly = isin_mps_friendly
    sys.modules["transformers.pytorch_utils"] = pu


def patch_is_torch_greater():
    """Add is_torch_greater_or_equal if missing."""
    try:
        from transformers.utils.import_utils import is_torch_greater_or_equal
        return
    except ImportError:
        pass

    try:
        import transformers.utils.import_utils as iu
        import torch
        from packaging import version

        def is_torch_greater_or_equal(target_version):
            return version.parse(torch.__version__) >= version.parse(target_version)

        iu.is_torch_greater_or_equal = is_torch_greater_or_equal
        sys.modules["transformers.utils.import_utils"] = iu
    except Exception:
        pass


def apply_patches():
    """Apply all compatibility patches."""
    patch_is_torch_greater()
    patch_transformers()


if __name__ == "__main__":
    apply_patches()
    # Verify
    from transformers.pytorch_utils import isin_mps_friendly
    print("✅ Patch applied: isin_mps_friendly is available")
