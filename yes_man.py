import ray
import pandas as pd
from configs.functions import get_datasets
from ray.tune.registry import register_env
# ! run só para ray 0.7 e nao ta funcionando
# from ray.tune import grid_search, run
from ray.tune import grid_search, run_experiments
from env.YesMan import TradingEnv

# ! ray 0.7.2 => user o run() e nao mais o run_experiments() https://ray.readthedocs.io/en/latest/tune-package-ref.html


# ? ja mandar as dfs separadas por asset para o GymEnv

class Trade:
    """Fertile environment to trade cryptos via algorithm"""

    def __init__(self, assets=['BTC', 'LTC', 'ETH'], currency='USDT', granularity='day', datapoints=600):

        self.assets = assets
        self.currency = currency
        self.granularity = granularity
        self.datapoints = datapoints
        self.df = {}
        self.config_spec = {}
        self.check_variables_integrity()
        self.populate_dfs()

    def check_variables_integrity(self):
        if type(self.assets) != list or len(self.assets) == 0:
            raise ValueError("Incorrect 'assets' value")
        if type(self.currency) != str:
            raise ValueError("Incorrect 'currency' value")
        if type(self.granularity) != str:
            raise ValueError("Incorrect 'granularity' value")
        if type(self.datapoints) != int or 1 > self.datapoints > 2000:
            raise ValueError("Incorrect 'datapoints' value")

    def populate_dfs(self):
        for asset in self.assets:
            self.df[asset] = {}
            self.df[asset]['train'], self.df[asset]['rollout'] = get_datasets(asset=asset,
                                                                              currency=self.currency,
                                                                              granularity=self.granularity,
                                                                              datapoints=self.datapoints)

    def generate_config_spec(self, lr_schedule):
        self.config_spec = {
            "lr_schedule": grid_search(lr_schedule),
            "env": "YesMan-v1",
            "num_workers": 3,  # parallelism
            'observation_filter': 'MeanStdFilter',
            'vf_share_layers': True,
            "env_config": {
                'assets': self.assets,
                'currency': self.currency,
                'granularity': self.granularity,
                'datapoints': self.datapoints,
                'df_complete': {},
                'df_features': {}
            },
        }
        self.add_dfs_to_config_spec(df_type='train')

    def add_dfs_to_config_spec(self, df_type):
        for asset in self.assets:
            self.config_spec['env_config']['df_complete'][asset] = self.df[asset][df_type]
            self.config_spec['env_config']['df_features'][asset] = self.df[asset][df_type].loc[:,
                                                                                               self.df[asset][df_type].columns != 'Date']

    def train(self, algo='PPO', timesteps=3e10, checkpoint_freq=100, lr_schedule=[[[0, 7e-5], [3e10, 7e-6]]]):
        register_env("YesMan-v1", lambda config: TradingEnv(config))
        ray.init()

        self.generate_config_spec(lr_schedule)

        # ! ray==6 functiona o run_experiments mas nao o run que nao functiona com nenhuma versao

        # run(name="experiment_name",
        #     run_or_experiment="PPO",
        #     stop={'timesteps_total': timesteps},
        #     checkpoint_freq=100,
        #     config=self.config_spec)

        config_spec = {
            "vai": {
                "run": "PPO",
                "env": "YesMan-v1",
                "stop": {
                    "timesteps_total": 1e6,  # 1e6 = 1M
                },
                "checkpoint_freq": 100,
                "checkpoint_at_end": True,
                "config": {
                    "lr_schedule": grid_search(lr_schedule),
                    'num_workers': 1,  # parallelism
                    'observation_filter': 'MeanStdFilter',
                    'vf_share_layers': True,  # testing
                    "env_config": {
                        'assets': self.assets,
                        'currency': self.currency,
                        'granularity': self.granularity,
                        'datapoints': self.datapoints,
                        'df_complete': {},
                        'df_features': {}
                    },
                }
            }
        }

        for asset in self.assets:
            config_spec['vai']['config']['env_config']['df_complete'][asset] = self.df[asset]['train']
            config_spec['vai']['config']['env_config']['df_features'][asset] = self.df[asset]['train'].loc[:,
                                                                                                 self.df[asset]['train'].columns != 'Date']
        run_experiments(experiments=config_spec)