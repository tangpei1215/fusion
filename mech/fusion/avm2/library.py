
import os.path
import sys
import urllib
import zipfile

try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from mech.fusion.avm2.swc import SwcData
from mech.fusion.avm2.constants import QName, packagedQName
from mech.fusion.avm2.abc_ import AbcFile
from mech.fusion.avm2.query import ClassDesc

from copy import copy

AllTypes    = {}
AllPackages = {}

ClassDesc.Library = None

class NativePackage(object):
    """
    This is a native flash namespace package. It represents parts of
    SWC libraries. It lazily loads the native classes it needs for
    speed.
    """
    def __init__(self, library, name):
        self._library = library
        self._name = name
        self._types = {}
        self._packages = {}
        self._modulename_prefixes = []

    def __copy__(self):
        inst = type(self)(self._library, self._name)
        inst._types = self._types
        inst._packages = self._packages
        # XXX: should we copy modulename_prefixes?
        return inst

    def __repr__(self):
        return "<native flash module '%s'>" % (self._name or "toplevel",)

    def __getattr__(self, attr):
        value = self._packages.get(attr, self._types.get(attr, None))
        if value is not None:
            setattr(self, attr, value)
            return value
        raise AttributeError(attr)

    def __getitem__(self, item): # for stuff with non-Python attribute name
        if "." in item:
            context = self
            for a in item.split("."):
                context = getattr(context, a)
            return context
        return getattr(self, item)

    def install_global(self, modulename_prefix=None):
        """
        This installs this package into the sys.modules dict so it
        can imported and accessed globally. The use of this function
        or the one for the entire Library is not recommended, as
        globals are evil and should not be depended on.
        """
        if modulename_prefix:
            mnp = modulename_prefix.strip(".")
            self._modulename_prefixes.append(mnp)
            sys.modules[("%s.%s" % (mnp, self._name)).strip(".")] = self
        else:
            self._modulename_prefixes.append(None)
            sys.modules[self._name] = self

    def uninstall_global(self):
        """
        If you ever feel like uninstalling the havoc called by globally
        screwing up your Python, you can do so. ;) This is a dumb
        uninstall, it does not put back what was there before if something
        was overwritten.
        """
        for prefix in self._modulename_prefixes:
            if self._modulename_prefixes:
                del sys.modules["%s.%s" % (prefix, self._name)]
            else:
                del sys.modules[self._name]

class Library(object):
    """
    A library, or all the types and packages in a SWC file.
    """

    Package = NativePackage

    def __init__(self, Types, Packages):
        AllTypes.update(Types)
        AllPackages.update(Packages)
        self.types        = Types
        self.packages     = Packages
        self.packagesflat = {}
        self.toplevel     = self.Package(self, "")
        self.build_package_tree(None, self.packages, self.toplevel)

    def __getattr__(self, attr):
        return getattr(self.toplevel, attr)

    @classmethod
    def gen_library_swcdata(cls, swcdata):
        """
        Generates a Library from a SwcData object.
        """
        return cls.gen_library_abc(swcdata.get_all_abcs())

    @classmethod
    def gen_library_swfdata(cls, swfdata):
        """
        Generates a Library from a SwfData object.
        """
        from mech.fusion.swf.swfdata import SwfData
        return cls.gen_library_abc(swfdata.collect_type(AbcFile))

    @classmethod
    def gen_library_abc(cls, abc):
        """
        Generates a Library from an ABC file. This may take a little while
        for all libraries to be parsed and working, so it is recommended that
        it is pickled using the save_pickledb and load_pickledb methods.
        """
        Types        = {}
        Packages     = {}
        PackagesFlat = {}

        def properties(inst):
            return [(name, type, bool(getter), bool(setter)) for (name, type,
                     getter, setter) in inst.properties.itervalues()]

        def fields(inst):
            return [(field.name,
                     field.type_name) for field in inst.fields.itervalues()]

        def methods(inst):
            return [(m.name, m.method.param_types,
                     m.method.return_type) for m in inst.methods.itervalues()]

        for inst in abc.instances:
            # Build our class declarations.
            desc = ClassDesc()
            desc.FullName      = inst.name
            desc.BaseType      = inst.super_name
            desc.Fields        = fields(inst)
            desc.StaticFields  = fields(inst.cls)
            desc.Methods       = methods(inst)
            desc.StaticMethods = methods(inst.cls)
            desc.Properties    = properties(inst)
            desc.StaticProperties = properties(inst.cls)

            # Set it up in the package.
            package = PackagesFlat.setdefault(desc.Package, {})
            Types[inst.name] = package[desc.ShortName] = desc

        for package, D in PackagesFlat.iteritems():
            # Go through and build our tree.
            parts = package.split(".")
            context = Packages
            for part in parts[:-1]:
                context = context.setdefault(part, {})
            context[parts[-1]] = D

        # Fix toplevel stuff.
        Packages.update(Packages[''])
        del Packages['']

        return cls(Types, Packages)

    @classmethod
    def load_pickledb(cls, picklepath):
        """
        Load a Library from a pickle object.
        """
        f = open(picklepath, "rb")
        obj = pickle.load(f)
        f.close()
        return obj

    def save_pickledb(self, picklepath):
        f = open(picklepath, "wb")
        pickle.dump(self, f)
        f.close()

    def __setstate__(self, state):
        types, packages = state
        self.__init__(types, packages)

    def __getstate__(self):
        return self.types, self.packages

    def build_package_tree(self, parentname, packagedict, context):
        """
        This function recursively builds the NativePackage objects from
        the tree generated by gen_library_abc.
        """
        self.packagesflat[parentname] = context
        for name, value in packagedict.iteritems():
            if parentname:
                packagename = "%s.%s" % (parentname, name)
            else:
                packagename = name
            if isinstance(value, dict):
                valuepackage = self.Package(self, packagename)
                self.build_package_tree(packagename, value, valuepackage)
                context._packages[name] = valuepackage
            else:
                value.Library = self
                context._types[name] = value

    ## def convert_classdesc(self, classdesc):
    ##     """
    ##     This is a hook to convert the ClassDesc objects in the pickle
    ##     database into something a little more reasonable for users of
    ##     this library.
    ##     """
    ##     return classdesc

    def get_type(self, name):
        """
        This function returns the object associated with the passed
        multiname in this library, and optionally calls
        self.convert_classdesc before returning it (default is True).
        """
        return self.types[name]

    def install_global(self, modulename_prefix=None):
        """
        This installs all packages in this library into the
        sys.modules dict so it can imported and accessed globally. The
        use of this function or the one for individual packages not
        recommended, as globals are evil and should not be depended on.
        """
        for pkg in self.packagesflat.itervalues():
            pkg.install_global(modulename_prefix)

def get_playerglobal_swc():
    """
    This downloads and "extracts" the playerglobal SWC from
    Adobe's official servers.
    """
    URL = "http://download.macromedia.com/pub/labs/flashplayer10/flashplayer10_globalswc.zip"
    zipf = zipfile.ZipFile(StringIO(urllib.urlopen(URL).read()))
    filename = next(f for f in zipf.namelist() if \
                    f.endswith("playerglobal.swc") and not \
                    f.startswith("__MACOSX"))
    return SwcData.from_file(StringIO(zipf.open(filename, "r").read()))

def gen_playerglobal(output, Library=Library):
    """
    This method does the entire "playerglobal" library generation.

    This adds some additional classes, so please use this for playerglobal
    instead of gen_library.
    """
    library = Library.gen_library_abc(get_playerglobal_swc().get_abc("library.swf"))
    
    # Special hack for Vector's public interface.
    Vector = copy(library.toplevel.__AS3__.vec.Vector)
    Vector.Specializable   = True
    Vector.SpecializedFast = {
        QName('int'): packagedQName('__AS3__.vec', 'Vector$int'),
        QName('uint'): packagedQName('__AS3__.vec', 'Vector$uint'),
        QName('Number'): packagedQName('__AS3__.vec', 'Vector$double'),
        QName('Object'): packagedQName('__AS3__.vec', 'Vector$object'),
    }
    library.types[packagedQName('__AS3__.vec', 'Vector')] = Vector
    library.toplevel.__AS3__.vec._types['Vector'] = Vector

    library.types[QName('Vector')] = Vector
    library.toplevel._types['Vector'] = Vector

    # And hack Object's super_name to be None.
    Object = library.toplevel.Object
    Object.BaseType = None

    library.save_pickledb(output)

def gen_library(swcpath, output, Library=Library):
    """
    This method does the entire generation process for a random SWC.
    """
    Library.gen_library_swcdata(SwcData.from_filename(swcpath)).save_pickledb(output)

def get_playerglobal(Library=Library):
    """
    This method loads and returns the playerglobal.pickle file that should
    be bundled with Mecheye Fusion.
    """
    return Library.load_pickledb(os.path.join(os.path.dirname(__file__), "playerglobal.pickle"))

def get_type(TYPE):
    """
    This function returns the object associated with the passed
    multiname in all installed libraries.
    """
    return AllTypes[QName(TYPE)]

def type_exists(TYPE):
    """
    This function checks for the existance of TYPE, a multiname, in all
    the currently installed libraries.
    """
    return QName(TYPE) in AllTypes

def librarygen_main():
    from optparse import OptionParser
    parser = OptionParser(usage="usage: %prog [-o DESTINATION] [-p | FILENAME]")
    parser.add_option("-p", "--playerglobal", action="store_true", dest="pg",
                      default=False, help="download and parse the playerglobal"
                      " file instead of a local file.")
    parser.add_option("-o", "--output", action="store", dest="output", default=None)
    options, args = parser.parse_args()
    if options.pg and args:
        parser.error("cannot use both --playerglobal and a FILENAME")
    elif options.pg:
        options.output = options.output or "playerglobal.pickle"
        print "Generating", options.output
        gen_playerglobal(options.output)
    elif not args:
        parser.error("no filename specified")
    elif len(args) > 1:
        parser.error("too many args")
    else:
        options.output = options.output or os.path.splitext(os.path.basename(args[0]))[0]+".pickle"
        print "Generating", options.output
        gen_library(args[0], options.output)
