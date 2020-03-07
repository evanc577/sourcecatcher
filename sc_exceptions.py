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
        return "No matches found. Possible reasons:"

    def reasons(self):
        reasons = [
                "Twitter is not the source of this image",
                "Sourcecatcher is not following the source Twitter user",
                "The source tweet was removed or deleted",
                "The image was heavily altered or cropped",
                "The source Twitter user deleted the tweet before Sourcecatcher analyzed it",
                "The source Twitter user tweeted more than 3200 times since the source tweet",
                "Sourcecatcher messed up",
                ]
        return reasons

class InvalidLink(SCError):
    """Raised when an invalid link is used"""

    def __str__(self):
        return "Could not find any data at this link"

class InvalidImage(SCError):
    """Raised when an image cannot be opened"""

    def __str__(self):
        return "Could not open image (is it actually an image?)"

class DCAppError(SCError):

    def __init__(self, reason):
        self.reason = reason

    def __str__(self):
        return f"Could not connect to DC app website ({self.reason})"

class TWError(SCError):

    def __init__(self, message, user=None, tweet_id=None):
        self.message = message
        self.link = None
        if user is not None and tweet_id is not None:
            self.link = f"https://twitter.com/{user}/status/{tweet_id}"

    def __str__(self):
        return f"A matching image was found but the tweet no longer exists ({self.message})"

class VideoDownloadError(SCError):

    def __str__():
        return "Could not download file"

class AnimatedGIFError(SCError):

    def __str__(self):
        return "Searching animated GIFs is not supported"
