# Skill dependency management.

from typing import List, Self

class Dependency:
    """
    Declares relationships between skills.  A dependency can be provided by
    one or more skills; it can grant zero or more 'free' skills when satisfied;
    it can be required by zero or more skills; and it can be wanted by skills
    that are documented to need it but don't actually require it to function.
    """

    def __init__(self, name : str) -> None:
        """
        Args:
            name : A human-friendly label for the dependency.  Used for logging.
        """
        self.name = name
        self.providers = []
        self.extra_skills = []
        self.dependers = []
        self.wanters = []

    def provided_by(self, providers : List[str]) -> Self:
        """
        Sets the skills that supply the dependency.  See the Builder pattern.

        Args:
            providers:  List of skills that fulfill the dependency.

        Returns:
            The Dependency, so that other builders can be chained.
        """
        self.providers = providers
        return self

    def grants(self, extra_skills : List[str]) -> Self:
        """
        Sets the skills supplied free by the dependency.  See the Builder
        pattern.

        Args:
            extra_skills:  List of skills granted by the dependency.

        Returns:
            The Dependency, so that other builders can be chained.
        """
        self.extra_skills = extra_skills
        return self

    def required_by(self, dependers : List[str]) -> Self:
        """
        Sets the skills that need the dependency.  See the Builder pattern.

        Args:
            dependers:  List of skills that need the dependency to function
                properly.

        Returns:
            The Dependency, so that other builders can be chained.
        """
        self.dependers = dependers
        return self

    def wanted_by(self, wanters : List[str]) -> Self:
        """
        Sets the skills that don't really need the dependency but are documented
            to require it.

        Args:
            wanters:  List of skills that want the dependency.

        Returns:
            The Dependency, so that other builders can be chained.
        """
        self.wanters = wanters
        return self
