import argparse
import json

def merge_config(parser, argv, config_file, flags=()):
    config = None
    with open(config_file) as f:
        config = json.load(f)
    if config is None:
        return None
    
    config_argv = []
    for k in config:
        opt = "--" + k
        v = config[k]
        if opt in flags:
            if v == True:
                config_argv.append(opt)
        else:
            config_argv.append(opt)
            config_argv.append(str(config[k]))
    
    # config の指定をマージして再パース(コマンドラインで指定された値が優先)
    new_argv = config_argv + argv[1:]
    #print("new_argv:" + str(new_argv))
    args = parser.parse_args(new_argv)
    #print("args:" + str(vars(args)))
    return args
