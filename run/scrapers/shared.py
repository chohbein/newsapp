import pandas as pd

class DataCollector:
    def __init__(self):
        self.data_list = []

    def append_data(self, new_data):
        self.data_list.append(new_data)

    def get_dataframe(self):
        return pd.DataFrame(self.data_list)

#   Thought there would be more. But just the data class for now. Too lazy to optimize just keep it
def init_shared_resources():
    collector = DataCollector()
    return collector