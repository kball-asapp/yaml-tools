import sys
import argparse
import ruamel.yaml
import re


def get_type_error(dest, src, current_path):
    return TypeError('Error trying to merge a {0} in a {1} at {2}'.format(type(src), type(dest), current_path))


def _merge(dest, src, current_path=""):
    """
    (Recursively) merge a source object to an dest object (CommentedMap, CommentedSeq or other object)
    and append the current position to current_path
    :return: the merged object
    """
    if isinstance(src, ruamel.yaml.comments.CommentedMap):
        if isinstance(dest, ruamel.yaml.comments.CommentedMap):
            for k in src:
                dest[k] = _merge(dest[k], src[k], current_path + '.' + str(k)) if k in dest else src[k]
                if k in src.ca._items and src.ca._items[k][2] and \
                        src.ca._items[k][2].value.strip():
                    dest.ca._items[k] = src.ca._items[k]  # copy non-empty comment
        else:
            raise get_type_error(dest, src, current_path)
    elif isinstance(src, ruamel.yaml.comments.CommentedSeq):
        if isinstance(dest, ruamel.yaml.comments.CommentedMap):
            raise get_type_error(dest, src, current_path)
        elif isinstance(dest, ruamel.yaml.comments.CommentedSeq):
            dest.extend(src)
        else:
            src.append(dest)
            dest = src
    else:
        if isinstance(dest, ruamel.yaml.comments.CommentedMap):
            raise get_type_error(dest, src, current_path)
        elif isinstance(dest, ruamel.yaml.comments.CommentedSeq):
            dest.append(src)
        else:
            dest = src
    return dest


def successive_merge(contents):
    """
    Successively merge a list of yaml contents by calling _merge()
    :param contents: list of yaml contents in str format
    :return: merged yaml in str format
    """
    data = []
    for i in contents:
        data.append(ruamel.yaml.round_trip_load(i))
    for i in range(-1, -len(contents), -1):
        _merge(data[i - 1], data[i], 'ROOT')
    return data[0]


def has_valid_brackets(s):
    """
    Check if the string s is in format "key[index]"
    :param s: e.g. my_list[0]
    :return: (True, key, index) or (None, None, None)
    """
    list_regex = re.compile(r"\A\w+\[{1}\d+\]{1}\Z")
    if list_regex.match(s) is not None:
        key = s[:int(s.find('['))]
        index = int(s[s.find('[') + 1: len(s) - 1])
        return True, key, index
    return None, None, None


def get_dict_item(dic, item):
    """
    Get one specific item from a dict
    :param dic: the dict
    :param item: a key or key[index], in string format
    :return: the wanted item if found, otherwise raises an error
    """
    is_array, key, index = has_valid_brackets(item)
    if is_array:  # if we want to access an item from an array
        try:
            got_item = dic[key][index]
        except IndexError:
            raise IndexError('list index out of range at "{}"'.format(item))
        except KeyError:
            raise TypeError("'{}' is not a list".format(key))

    else:  # simple dict get
        got_item = dic[item]
    return got_item


def get_dict_item_from_path(dic, path):
    """
    Utility function to get one specific item from a dict given his "path" (in str format, e.g. "key1.list_key[0].key2")
    :return: the item if found
    """
    if path == '':
        return dic

    path_to_item = path.split('.')

    curr = dic
    for p in path_to_item:
        curr = get_dict_item(curr, p)
    return curr


def delete():
    """
    Sub-command, see main()
    """
    parser = argparse.ArgumentParser(description='Delete one item from the input yaml file')
    parser.add_argument('item_path', type=str, help='<Required> Yaml item to be deleted, e.g. "key1.list[0].key2"')
    parser.add_argument('-i', '--input', type=str, help='<Required> Path to the input yaml files', required=True)
    parser.add_argument('-o', '--output', type=str, help='Path to the output file, or stdout by default')
    parser.add_argument('--indent', type=int, help='Number of space(s) for each indent', default=2)

    args = parser.parse_args(sys.argv[2:])
    input_file = open(args.input, 'r')
    data = ruamel.yaml.round_trip_load(input_file.read())
    input_file.close()

    path_list = args.item_path.split('.')
    item_parent = get_dict_item_from_path(data, '.'.join(path_list[:-1]))

    item_to_delete = path_list[-1]
    is_array, key, index = has_valid_brackets(item_to_delete)
    try:
        if is_array:
            item_parent[key][index]  # to trigger a KeyError if not found
            del item_parent[key][index]
        else:
            item_parent[item_to_delete]
            del item_parent[item_to_delete]
    except (AttributeError, KeyError, IndexError, TypeError):
        print("An error occurred when deleting '{}' :".format(item_to_delete))
        raise

    output_file = open(args.output, 'w') if args.output else sys.stdout
    ruamel.yaml.round_trip_dump(data, output_file, indent=args.indent)
    output_file.close()


def merge():
    """
    Sub-command, see main()
    """
    parser = argparse.ArgumentParser(description='Merge two or more yaml files and preserve the comments')
    parser.add_argument('-i', '--inputs', nargs='+', type=str, help='<Required> List of input yaml files',
                        required=True)
    parser.add_argument('-o', '--output', type=str, help='Path to the output file, or stdout by default')
    parser.add_argument('--indent', type=int, help='Number of space(s) for each indent', default=2)

    args = parser.parse_args(sys.argv[2:])

    file_contents = []
    for f in args.inputs:
        file = open(f, 'r')
        file_contents.append(file.read())
        file.close()

    out_content = successive_merge(file_contents)
    output_file = open(args.output, 'w') if args.output else sys.stdout
    ruamel.yaml.round_trip_dump(out_content, output_file, indent=args.indent)
    output_file.close()


def main():
    parser = argparse.ArgumentParser(
        description='A set of CLI tools to manipulate YAML files (merge, delete, etc...) with comment preservation',
        usage='''yaml-tools <command> [<args>]
At the moment there are only two commands available:
   merge     Merge two or more yaml files and preserve the comments
   delete    Delete one item from the input yaml file''')
    parser.add_argument('command', help='Sub-command to run')
    # parse_args defaults to [1:] for args, but you need to
    # exclude the rest of the args too, or validation will fail
    args = parser.parse_args(sys.argv[1:2])
    if args.command == 'merge':
        merge()
    elif args.command == 'delete':
        delete()
    else:
        print('Unrecognized command')
        parser.print_help()
        exit(1)


if __name__ == '__main__':  # pragma: no cover
    main()
