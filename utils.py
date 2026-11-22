from requests import RequestException


def get_orcid_name(api, orcid):
    try:
        token = api.get_search_token_from_orcid()
        user_data = api.read_record_public(orcid, 'record', token)
        name = ''
        if user_data["person"]["name"] is not None:
            if user_data["person"]["name"]["given-names"] is not None:
                name += user_data["person"]["name"]["given-names"]["value"]
                if user_data["person"]["name"]["family-name"] is not None:
                    name += " " + user_data["person"]["name"]["family-name"]["value"]
            else:
                if user_data["person"]["name"]["family-name"] is not None:
                    name += user_data["person"]["name"]["family-name"]["value"]

    except RequestException:
        name = ''
    return name


def checksum(x):
    """ Routine to verify ORCID checksum """
    total = 0
    for s in x[:-1]:
        if s == "-":
            continue
        total = 2 * (total + int(s))

    remainder = total % 11
    result = (12 - remainder) % 11

    if (result == 10) and (x[-1] == "X"):
        return True
    elif result == int(x[-1]):
        return True
    else:
        return False
