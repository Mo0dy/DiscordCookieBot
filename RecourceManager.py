import pickle


def save_dict(d, name):
    with open(name + '.pkl', 'wb') as f:
        pickle.dump(d, f, pickle.HIGHEST_PROTOCOL)


def load_dict(name):
    try:
        with open(name + '.pkl', 'rb') as f:
            d = pickle.load(f)
    except FileNotFoundError:
        print("ERROR tried to load %s but file not found" % name)
        d = {}
    return d


def load_token(path):
    """returns the first word in a text file

    :param path:
    :return:
    """
    with open(path) as f:
        return f.readlines()[0].strip()
