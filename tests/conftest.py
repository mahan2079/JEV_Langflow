import sys
from unittest.mock import MagicMock

# Create mock module hierarchy for lfx so components can be tested and imported outside full Langflow container
if "lfx" not in sys.modules:
    lfx = MagicMock()
    
    class MockComponent:
        def __init__(self, **kwargs):
            # Populate default input values from self.inputs
            if hasattr(self.__class__, "inputs"):
                for inp in self.__class__.inputs:
                    if hasattr(inp, "name"):
                        setattr(self, inp.name, getattr(inp, "value", None))
            for k, v in kwargs.items():
                setattr(self, k, v)

    class MockInput:
        def __init__(self, name=None, display_name=None, value=None, **kwargs):
            self.name = name
            self.display_name = display_name
            self.value = value
            for k, v in kwargs.items():
                setattr(self, k, v)

    class MockOutput:
        def __init__(self, name=None, display_name=None, method=None, **kwargs):
            self.name = name
            self.display_name = display_name
            self.method = method

    class MockData:
        def __init__(self, data=None, text_key=None, **kwargs):
            self.data = data or {}
            self.text_key = text_key

    class MockMessage:
        def __init__(self, text="", **kwargs):
            self.text = text

    class MockDataFrame:
        def __init__(self, df=None, **kwargs):
            self.df = df

        @classmethod
        def from_records(cls, records):
            return cls(df=records)

    lfx.custom.custom_component.component.Component = MockComponent
    lfx.io.DataInput = MockInput
    lfx.io.FloatInput = MockInput
    lfx.io.IntInput = MockInput
    lfx.io.StrInput = MockInput
    lfx.io.BoolInput = MockInput
    lfx.io.MultilineInput = MockInput
    lfx.io.TableInput = MockInput
    lfx.io.DropdownInput = MockInput
    lfx.io.SecretStrInput = MockInput
    lfx.io.MessageTextInput = MockInput
    lfx.io.NestedDictInput = MockInput
    lfx.io.Output = MockOutput
    lfx.schema.data.Data = MockData
    lfx.schema.message.Message = MockMessage
    lfx.schema.dataframe.DataFrame = MockDataFrame

    sys.modules["lfx"] = lfx
    sys.modules["lfx.custom"] = lfx.custom
    sys.modules["lfx.custom.custom_component"] = lfx.custom.custom_component
    sys.modules["lfx.custom.custom_component.component"] = lfx.custom.custom_component.component
    sys.modules["lfx.io"] = lfx.io
    sys.modules["lfx.schema"] = lfx.schema
    sys.modules["lfx.schema.data"] = lfx.schema.data
    sys.modules["lfx.schema.message"] = lfx.schema.message
    sys.modules["lfx.schema.dataframe"] = lfx.schema.dataframe
