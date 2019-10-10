class SCError(Exception):
    pass

class EntityTooLarge(SCError):
    """Raised when submitted file is too large"""

    def __str__(self):
        return "The submitted file was too large (max 15MB)"

class InvalidDCAppLink(SCError):
    """Raised when an invalid Dreamcatcher app link is submitted"""

    def __str__(self):
        return "Invalid Dreamcatcher app url"

class FullSizeDCAppImage(SCError):
    """Raised when a direct link to a Dreamcatcher app image is already full size"""

    def __str__(self):
        return "Invalid Dreamcatcher app url, or the image is already full size"

class NoMatchesFound(SCError):
    """Raised when no matching images are found"""

    def __str__(self):
        return "No matches found"

class InvalidLink(SCError):
    """Raised when an invalid link is used"""

    def __str__(self):
        return "Invalid link"

class InvalidImage(SCError):
    """Raised when an image cannot be opened"""

    def __str__(self):
        return "Could not open image (is it actually an image?)"
