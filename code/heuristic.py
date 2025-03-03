
import os


def create_key(template, outtype=('nii.gz',), annotation_classes=None):
    if template is None or not template:
        raise ValueError('Template must be a valid format string')
    return template, outtype, annotation_classes


def infotodict(seqinfo):
    """Heuristic evaluator for determining which runs belong where

    allowed template fields - follow python string module:

    item: index within category
    subject: participant id
    seqitem: run number during scanning
    subindex: sub index within group
    """

    # structurals
    t1w = create_key(
        "sub-{subject}/{session}/anat/sub-{subject}_{session}_T1w"
    )
    t2w = create_key(
        "sub-{subject}/{session}/anat/sub-{subject}_{session}_T2w"
    )

    # functionals
    mist = create_key(
        "sub-{subject}/{session}/func/sub-{subject}_{session}_task-mist_run-{item:02d}_bold"
    )
    mpt = create_key(
        "sub-{subject}/{session}/func/sub-{subject}_{session}_task-mpt_run-{item:02d}_bold"
    )
    sorpf = create_key(
        "sub-{subject}/{session}/func/sub-{subject}_{session}_task-sorpf_run-{item:02d}_bold"
    )
    rest_sbref = create_key(
        "sub-{subject}/{session}/func/sub-{subject}_{session}_task-rest_run-{item:02d}_sbref"
    )
    rest_bold = create_key(
        "sub-{subject}/{session}/func/sub-{subject}_{session}_task-rest_run-{item:02d}_bold"
    )

    # field maps
    fmap_func_1 = create_key("sub-{subject}/{session}/fmap/sub-{subject}_{session}_acq-{acquisition}_dir-{direction}_run-01_epi")
    fmap_func_2 = create_key("sub-{subject}/{session}/fmap/sub-{subject}_{session}_acq-{acquisition}_dir-{direction}_run-02_epi")
    fmap_func_3 = create_key("sub-{subject}/{session}/fmap/sub-{subject}_{session}_acq-{acquisition}_dir-{direction}_run-03_epi")
    fmap_func_4 = create_key("sub-{subject}/{session}/fmap/sub-{subject}_{session}_acq-{acquisition}_dir-{direction}_run-04_epi")
    fmap_func_5 = create_key("sub-{subject}/{session}/fmap/sub-{subject}_{session}_acq-{acquisition}_dir-{direction}_run-05_epi")
    fmap_func_6 = create_key("sub-{subject}/{session}/fmap/sub-{subject}_{session}_acq-{acquisition}_dir-{direction}_run-06_epi")

    info = {
        t1w: [],
        t2w: [],
        mist: [],
        mpt: [],
        sorpf: [],
        rest_sbref: [],
        rest_bold: [],
        fmap_func_1: [],
        fmap_func_2: [],
        fmap_func_3: [],
        fmap_func_4: [],
        fmap_func_5: [],
        fmap_func_6: [],
    }

    for i, s in enumerate(seqinfo):
        xdim, ydim, slice_num, timepoints = (s[6], s[7], s[8], s[9])

        # Structural scans:
        if (slice_num == 176) and (timepoints == 1) and ("NORM" in s.image_type):
            if "T1w" in s[12]:
                info[t1w].append([s[2]])
            elif "T2w" in s[12]:
                info[t2w].append([s[2]])

        # Functional Task Scans:
        elif "task" in s[12]:
            if (s[12].endswith("MIST1")) or (
                s[12].endswith("MIST2")
            ):
                info[mist].append(s[2])
            elif (s[12].endswith("MPT1")) or (
                s[12].endswith("MPT2")) or (
                s[12].endswith("MPT3")) or (
                s[12].endswith("MPT4")
            ):
                info[mpt].append(s[2])
            elif (s[12].endswith("SORPF1")) or (
                s[12].endswith("SORPF2")
            ):
                info[sorpf].append(s[2])

        # Resting-State Scans:
        elif "REST" in s[12]:
            if timepoints == 10:
                info[rest_sbref].append(s[2])
            elif (slice_num == 72) and (timepoints == 2045) and ("NORM" in s.image_type):
                info[rest_bold].append(s[2])
        
        # Field Maps:
        elif (("DistortionMap" in s[12]) or ("fmap" in s[12])) and ((xdim, ydim, slice_num) == (90, 90, 60) or (xdim, ydim, slice_num) == (110, 110, 360)) and timepoints == 1:
            direction = "PA" if "PA" in s[12] else "AP"

            # Look for task scans 2 rows below field map
            if i + 2 < len(seqinfo):
                next_scan = seqinfo[i + 2]
                if "fMRI_task_MPT1" in next_scan[12] or "fMRI_task_MPT2" in next_scan[12]:
                    info[fmap_func_1].append(
                        {"item": s[2], "direction": direction, "acquisition": "func"}
                    )
                elif "fMRI_task_MPT3" in next_scan[12] or "fMRI_task_MPT4" in next_scan[12]:
                    info[fmap_func_2].append(
                        {"item": s[2], "direction": direction, "acquisition": "func"}
                    )
                elif "fMRI_task_SORPF" in next_scan[12]:  # If SORPF is next
                    info[fmap_func_3].append(
                        {"item": s[2], "direction": direction, "acquisition": "func"}
                    )
                elif "fMRI_task_MIST" in next_scan[12]:  # If MIST is next
                    info[fmap_func_4].append(
                        {"item": s[2], "direction": direction, "acquisition": "func"}
                    )
                elif "REST1" in next_scan[12]:  # If REST1 is next
                    info[fmap_func_5].append(
                        {"item": s[2], "direction": direction, "acquisition": "func"}
                    )
                elif "REST2" in next_scan[12]:  # If REST2 is next
                    info[fmap_func_6].append(
                        {"item": s[2], "direction": direction, "acquisition": "func"}
                    )

        else:
            pass

    return info