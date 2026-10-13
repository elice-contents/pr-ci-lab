def remaining_quota(limit, used):
    if limit < 0 or used < 0:
        raise ValueError("negative quota")
    return max(0, limit - used)
