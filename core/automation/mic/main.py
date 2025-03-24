class MicrophoneManager:
    def __init__(self):
        self.isMuted = False

    def mute(self):
        self.isMuted = True

    def unmute(self):
        self.isMuted = False

    def getMicStatus(self):
        return self.isMuted