import argparse
import json

def merge_config(parser, argv, config_file):
    config = None
    with open(config_file) as f:
        config = json.load(f)
    if config is None:
        return None
    
    config_argv = []
    for k in config:
        config_argv.append("--" + k)
        config_argv.append(str(config[k]))
    
    # config の指定をマージして再パース(コマンドラインで指定された値が優先)
    new_argv = config_argv + argv[1:]
    #print("new_argv:" + str(new_argv))
    args = parser.parse_args(new_argv)
    #print("args:" + str(vars(args)))
    return args
