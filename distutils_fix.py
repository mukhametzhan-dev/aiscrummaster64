# Compatibility fix for undetected-chromedriver with Python 3.12+
# This file provides a workaround for the distutils.version import error

try:
    from packaging.version import Version
    
    # Create a wrapper that mimics distutils.version.LooseVersion behavior
    class LooseVersion(Version):
        def __init__(self, version):
            if hasattr(version, 'version'):
                version_str = version.version
            else:
                version_str = str(version)
            super().__init__(version_str)
            self.vstring = version_str
            self.version = [int(x) for x in version_str.split('.') if x.isdigit()]
            
except ImportError:
    try:
        from distutils.version import LooseVersion
    except ImportError:
        # Last resort - create a simple version comparison class
        class LooseVersion:
            def __init__(self, version):
                if hasattr(version, 'version'):
                    version_str = version.version
                else:
                    version_str = str(version)
                self.vstring = version_str
                self.version = [int(x) for x in version_str.split('.') if x.isdigit()]
            
            def __str__(self):
                return self.vstring
            
            def __lt__(self, other):
                return self.version < other.version
            
            def __le__(self, other):
                return self.version <= other.version
            
            def __gt__(self, other):
                return self.version > other.version
            
            def __ge__(self, other):
                return self.version >= other.version
            
            def __eq__(self, other):
                return self.version == other.version
            
            def __ne__(self, other):
                return self.version != other.version

# Monkey patch distutils.version if it doesn't exist
import sys
if 'distutils' not in sys.modules:
    import types
    distutils = types.ModuleType('distutils')
    version = types.ModuleType('version')
    version.LooseVersion = LooseVersion
    distutils.version = version
    sys.modules['distutils'] = distutils
    sys.modules['distutils.version'] = version