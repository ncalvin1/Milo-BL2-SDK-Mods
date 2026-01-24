# Store and unroll changes to Unreal Engine objects.

import re
import unrealsdk
from mods_base import ENGINE
from typing import TYPE_CHECKING, Any

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
                obj: unrealsdk.unreal.UObject,
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

        key = obj._path_name() + "." + property_name
        if not key in self.cache:
            old_value = getattr(obj, property_name)
            self.undo_log.insert(
                0,
                self.get_command(obj._path_name(),
                                 property_name,
                                 old_value))
        self.cache[key] = new_value

    def set_obj_direct(self,
                       obj : unrealsdk.unreal.UObject,
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

        if isinstance(new_value, unrealsdk.unreal.UObject):
            self.undo_log.insert(0, (obj.Class, obj._path_name(),
                                     property_name,
                                     None,
                                     new_value.Class.Name,
                                     new_value._path_name()))
        else:
            self.undo_log.insert(0, (obj.Class, obj._path_name(),
                                     property_name,
                                     new_value,
                                     None,
                                     None))
        if self.verbose:
            unrealsdk.logging.warning("Direct set: %s.%s = %s." % (
                obj._path_name(),
                property_name,
                self.console_value(new_value))) 
        setattr(obj, property_name, new_value)

    def edit_obj(self,
                 obj: unrealsdk.unreal.UObject,
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

        key = obj._path_name() + "." + property_name
        if key in self.cache:
            # old value is already recorded in undo_log
            new_toplevel = self.cache[key]
        else:
            #old_toplevel = self.convert_to_python(getattr(obj, property_name))
            old_toplevel = getattr(obj, property_name)
            self.undo_log.insert(
                0,
                self.get_command(
                    obj._path_name(),
                    property_name,
                    old_toplevel))
            if old_toplevel is None:
                new_toplevel = property_type()
            else:
                if not isinstance(old_toplevel, property_type):
                    unrealsdk.logging.warning("Warning: %s is %s, not %s." %
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
        if isinstance(arg, List) or isinstance(arg,
                                               unrealsdk.unreal.WrappedArray):
            return [self.convert_to_python(element) for element in arg]
        if isinstance(arg, unrealsdk.unreal.WrappedStruct):
            type_name = str(arg.structType).rsplit(".", 1)[1]
            try:
                tuple_type = getattr(Mods.Structs, type_name)
                return tuple_type(arg)
            except AttributeError as ex:
                unrealsdk.logging.warning("Can't convert fstruct class %s." % (type_name))
                raise ex
        return arg  # hope I don't need to do a deep copy here

    def commit(self):
        """
        Write all changes from the cache to the game engine.  Call this BEFORE
        returning control to the game - otherwise Unreal object pointers are
        likely to start dangling.
        """

        actor = ENGINE.GamePlayers[0].Actor
        for key, toplevel in self.cache.items():
            obj_name, property_name = key.rsplit(".", 1)
            command = self.get_command(obj_name, property_name, toplevel)
            if self.verbose:
                unrealsdk.logging.warning("Executing commit: %s" % (command))
            actor.ConsoleCommand(command)
        self.cache = {}

    def unwind(self):
        """
        Revert all changes made to the game engine, in reverse order of how
        they were applied.
        """

        actor = ENGINE.GamePlayers[0].Actor
        for undo in self.undo_log:
            if isinstance(undo, str):
                if self.verbose:
                    unrealsdk.logging.warning("Executing undo: %s" % (undo))
                actor.ConsoleCommand(undo)
                continue
            (obj_class, obj_name, property_name,
             simple_value, ref_class, ref_name) = undo
            obj = unrealsdk.find_object(obj_class, obj_name)
            if obj is None:
                unrealsdk.logging.warning("Warning: can't find %s'%s' for undo" %
                              (obj_class, obj_name))
            elif ref_class is None:
                if self.verbose:
                    unrealsdk.logging.warning("Direct undo: %s.%s = %s." % (
                        obj._path_name(),
                        property_name,
                        self.console_value(simple_value)))
                setattr(obj, property_name, simple_value)
            else:
                ref = unrealsdk.find_object(ref_class, ref_name)
                if self.verbose:
                    unrealsdk.logging.warning("Direct undo: %s.%s = %s'%s'." % (
                        obj._path_name(),
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

    # Match single-quoted strings or collections of non-single-quote chars.
    RE_QUOTES = r"('[^']*')|([^']+)"
    
    # Match an enum specifier like <EModifierType.MT_Scale: 0.0>
    RE_ENUM = r'<[^:]+: (\d+\.?\d*)>'

    # Track if the quoted string is a literal or an object name.
    _is_object_name : bool = False
    
    @classmethod
    def convert_repr_to_console(cls, match: re.Match) -> str:
        """
        Helper function to convert WrapperStruct printed output to a form
        compatible with the UE console.

        Args:
            match:  Match group supplied by re.sub.

        Returns:
            The group modified to work on UE Console.
        """
        if match.group(2) is None:
            # Matched quoted text.
            if cls._is_object_name:
                cls._is_object_name = False
                return match.group(1)
            else:
                # String literal - double-quote it.
                return match.group(1).replace("'","\"")

        # If the non-quote characters end in an alphabetic char, a quoted
        # object name likely follows.
        if match.group(2)[-1:].isalpha():
            cls._is_object_name = True
            
        # Matched a series of non-quote characters outside all quotes.
        result = re.sub(Changes.RE_ENUM, r"\1", match.group(2))
        result = result.replace("{", "(").replace("}", ")")
        result = result.replace("[", "(").replace("]", ")")
        result = result.replace(": ", "=").replace(", ", ",")
        result = result.replace("()", "")

        return result
        
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
        elif type(value) == unrealsdk.unreal.UObject:
            value_text = f"{value.Class.Name}\'{value._path_name()}\'"
        elif type(value) == unrealsdk.unreal.WrappedStruct:
            #value = self.convert_to_python(value)
            if isinstance(value, tuple):
                value_text = "(" + ",".join([
                    field_name + "=" +
                    self.console_value(getattr(value, field_name, None))
                    for field_name in value._fields]) + ")"
            else:
                # Convert WrappedStruct repr to console format.
                self._is_object_name = False
                value_text = re.sub(
                    Changes.RE_QUOTES,
                    Changes.convert_repr_to_console,
                    str(value)
                )
        elif type(value) == list or type(value) == unrealsdk.unreal.WrappedArray:
            #if len(value) == 0:
            #    value_text = ""  # UE console doesn't like empty lists
            #else:
            value_text = "(" + ",".join([
                self.console_value(element)
                for element in value]) + ")"
        elif isinstance(value, tuple):
            # WrappedStruct conversion
            value_text = "(" + ",".join([
                field_name + "=" +
                self.console_value(getattr(value, field_name, None))
                for field_name in value._fields]) + ")"
        else:
            # Int, Bool, Enumval, ?
            # Pass stringified version and hope.
            value_text = str(value)
        return value_text
    

    
