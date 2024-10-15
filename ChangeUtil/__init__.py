import json
from collections import namedtuple
from typing import Set, List, Dict, Tuple, Any

import unrealsdk
from ..ModManager import SDKMod, RegisterMod
from Mods.ModMenu import Game, ModTypes, ModPriorities, EnabledSaveType

try:
    import Mods.Structs
except ImportError as ex:
    import webbrowser
    webbrowser.open("https://bl-sdk.github.io/requirements/?mod=ChangeUtil&Structs")
    raise ex


__VERSION_INFO__: Tuple[int, ...] = (0, 1)
__VERSION__: str = ".".join(map(str, __VERSION_INFO__))


class Changes:
    """
    Changes proxies modifications to BL2/TPS game data, storing the original
       values of objects so that the changes may be reverted later.

    Properties:
        verbose (bool):  Set this to True to log all changes and reverts.
    """

    def __init__(self):
        self.undo_log = []
        self.cache = {}
        self.verbose = False

    def set_obj(self,
                obj: unrealsdk.UObject,
                property_name: str,
                new_value: Any) -> None:
        """
        Assign a new value to a toplevel property of an object.  The assignment
        does not actually happen until commit() is invoked.  Use this only if
        completely replacing a property value at toplevel; if modifying existing
        structs or arrays, use edit_obj instead.

        Args:
            obj:  The UnrealEngine object to modify.
            property_name:  The object property being modified.
            new_value:  The value to assign to the object's property.  This
                can be a primitive value, a sequence, an FArray, a
                NamedTuple, or another UObject.  This should NOT be a custom
                Python class or an advanced collection like a heap.
        """

        key = obj.GetObjectName() + "." + property_name
        if not key in self.cache:
            old_value = getattr(obj, property_name)
            self.undo_log.insert(
                0,
                self.get_command(obj.GetObjectName(),
                                 property_name,
                                 old_value))
        self.cache[key] = new_value

    def set_obj_direct(self,
                       obj : unrealsdk.UObject,
                       property_name : str,
                       new_value : Any) -> None:
        """
        Assign a new value to a toplevel property of an object.  The assignment
        happens immediately, rather than waiting for commit().  Note that this
        bypasses the console, so it should not be used to edit hotfixed objects
        or set internationalized strings.

        Args:
            obj:  The UnrealEngine object to modify.
            property_name:  The object property being modified.
            new_value:  The value to assign to the object's property.  This
                can be a primitive value, a sequence, an FArray, a
                NamedTuple, or another UObject.  This should NOT be a custom
                Python class or an advanced collection like a heap.
        """

        if isinstance(new_value, unrealsdk.UObject):
            self.undo_log.insert(0, (obj.Class, obj.GetObjectName(),
                                     property_name,
                                     None,
                                     new_value.Class.Name,
                                     new_value.GetObjectName()))
        else:
            self.undo_log.insert(0, (obj.Class, obj.GetObjectName(),
                                     property_name,
                                     new_value,
                                     None,
                                     None))
        if self.verbose:
            unrealsdk.Log("Direct set: %s.%s = %s." % (
                obj.GetObjectName(),
                property_name,
                self.console_value(new_value))) 
        setattr(obj, property_name, new_value)

    def edit_obj(self,
                 obj: unrealsdk.UObject,
                 property_name: str,
                 property_type: type) -> Any:
        """
        Mark a toplevel property of an object as changed, and open it for
        editing.  Subsequent changes to the returned property do not actually
        happen until commit() is invoked, which also terminates the edit.  Use
        this to make small changes to complex structs or arrays.  Note that
        resizing an array is not currently feasible with this method; use
        set_obj instead.  The returned value is not thread-safe, as it will
        pick up changes from any simultaneous attempts to edit the same
        property.

        Args:
            obj:  The UnrealEngine object to modify.
            property_name:  The object property being modified.
            property_type:  The type to use for the property's value, in case
                the existing value is None.

        Returns:
            Any:  The property's value at the time edit_obj was called.  Make
                desired edits to this object before calling commit().
        """

        key = obj.GetObjectName() + "." + property_name
        if key in self.cache:
            # old value is already recorded in undo_log
            new_toplevel = self.cache[key]
        else:
            old_toplevel = self.convert_to_python(getattr(obj, property_name))
            self.undo_log.insert(
                0,
                self.get_command(
                    obj.GetObjectName(),
                    property_name,
                    old_toplevel))
            if old_toplevel is None:
                new_toplevel = property_type()
            else:
                if not isinstance(old_toplevel, property_type):
                    unrealsdk.Log("Warning: %s is %s, not %s." %
                                  (key, type(old_toplevel), property_type))
                new_toplevel = old_toplevel
            self.cache[key] = new_toplevel
        return new_toplevel

    def convert_to_python(self, arg: Any) -> Any:
        """
        Recursively convert a UEScript object to an easier-to-work-with Python
        objects.  Code borrowed from the Structs mod.

        args:
          arg:  UEScript object to convert to a Python object.
        
        returns:
          Any:  A sequence, NamedTuple, or primitive corresponding to the
              UEScript object.

        raises:
          AttributeError if the converter encounters an unknown object type
        """

        if arg is None:
            return None
        if isinstance(arg, List) or isinstance(arg, unrealsdk.FArray):
            return [self.convert_to_python(element) for element in arg]
        if isinstance(arg, unrealsdk.FStruct):
            type_name = str(arg.structType).rsplit(".", 1)[1]
            try:
                tuple_type = getattr(Mods.Structs, type_name)
                return tuple_type(arg)
            except AttributeError as ex:
                unrealsdk.Log("Can't convert fstruct class %s." % (type_name))
                raise ex
        return arg  # hope I don't need to do a deep copy here

    def commit(self):
        """
        Write all changes from the cache to the game engine.  Call this BEFORE
        returning control to the game - otherwise Unreal object pointers are
        likely to start dangling.
        """

        actor = unrealsdk.GetEngine().GamePlayers[0].Actor
        for key, toplevel in self.cache.items():
            obj_name, property_name = key.rsplit(".", 1)
            command = self.get_command(obj_name, property_name, toplevel)
            if self.verbose:
                unrealsdk.Log("Executing commit: %s" % (command))
            actor.ConsoleCommand(command)
        self.cache = {}

    def unwind(self):
        """
        Revert all changes made to the game engine, in reverse order of how
        they were applied.
        """

        actor = unrealsdk.GetEngine().GamePlayers[0].Actor
        for undo in self.undo_log:
            if isinstance(undo, str):
                if self.verbose:
                    unrealsdk.Log("Executing undo: %s" % (undo))
                actor.ConsoleCommand(undo)
                continue
            (obj_class, obj_name, property_name,
             simple_value, ref_class, ref_name) = undo
            obj = unrealsdk.FindObject(obj_class, obj_name)
            if obj is None:
                unrealsdk.Log("Warning: can't find %s'%s' for undo" %
                              (obj_class, obj_name))
            elif ref_class is None:
                if self.verbose:
                    unrealsdk.Log("Direct undo: %s.%s = %s." % (
                        obj.GetObjectName(),
                        property_name,
                        self.console_value(simple_value)))
                setattr(obj, property_name, simple_value)
            else:
                ref = unrealsdk.FindObject(ref_class, ref_name)
                if self.verbose:
                    unrealsdk.Log("Direct undo: %s.%s = %s'%s'." % (
                        obj.GetObjectName(),
                        property_name,
                        ref_class,
                        ref_name))
                setattr(obj, property_name, ref)
        self.undo_log = []
        
    def get_command(self,
                    obj_name: str,
                    property_name: str,
                    new_value: Any) -> str:
        """
        Construct a console command to set the object's property to the new
        value.

        args:
            obj_name:  Name of the object to modify.
            property:  Name of the property to set.
            new_value:  Value to assign to the property.

        returns:
            str:  A UE console command to perform the assignment.

        """
        value_text = self.console_value(new_value)
        return f"set {obj_name} {property_name} {value_text}"

    def console_value(self, value: Any) -> str:
        """
        Translate a Python primitive or collection into its UE console format.

        args:
            value:  Python primitive or collection to translate.

        returns:
            str:  The UE console representation of the value.
        """

        if value is None:
            value_text = "None"
        elif type(value) == str:
            value_text = value
        elif type(value) == float:
            value_text = f"{value:.6f}"
        elif type(value) == unrealsdk.UObject:
            value_text = value.GetFullName().replace(" ","'") + "'"
        elif type(value) == unrealsdk.FStruct:
            value = self.convert_to_python(value)
            if isinstance(value, tuple):
                value_text = "(" + ",".join([
                    field_name + "=" +
                    self.console_value(getattr(value, field_name, None))
                    for field_name in value._fields]) + ")"
            else:
                value_text = "(ERROR)"
        elif type(value) == list or type(value) == unrealsdk.FArray:
            #if len(value) == 0:
            #    value_text = ""  # UE console doesn't like empty lists
            #else:
            value_text = "(" + ",".join([
                self.console_value(element)
                for element in value]) + ")"
        elif isinstance(value, tuple):
            # FStruct conversion
            value_text = "(" + ",".join([
                field_name + "=" +
                self.console_value(getattr(value, field_name, None))
                for field_name in value._fields]) + ")"
        else:
            # Int, Bool, Enumval, ?
            # Pass stringified version and hope.
            value_text = str(value)
        return value_text


# Stub to show mod is loaded
class _ChangeUtil(SDKMod):
    Name: str = "ChangeUtil"
    Author: str = "Milo"
    Description: str = "Tracks and reverts mod changes to BL2/TPS data."
    Version: str = __VERSION__
    Types: ModTypes = ModTypes.Library
    Priority: ModPriorities = ModPriorities.Library
    SupportedGames: Game = Game.BL2 | Game.TPS | Game.AoDK
    SaveEnabledState: EnabledSaveType = EnabledSaveType.NotSaved

    Status: str = "<font color=\"#00FF00\">Loaded</font>"
    SettingsInput: Dict[str, str] = {}

RegisterMod(_ChangeUtil())
