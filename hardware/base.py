from abc import ABC, abstractmethod

class AbstractCamera(ABC):
    @abstractmethod
    def open(self): pass
    @abstractmethod
    def start(self, fps): pass
    @abstractmethod
    def grab(self): pass
    @abstractmethod
    def close(self): pass