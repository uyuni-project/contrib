import argparse

import smtools

__smt = None

# --- Function to create image profile ---
def create_image_profile(args):
    """
    Create the image profile
    :param args: Argument list
    :return: True on success, False on failure
    """
    smt.log_info(f"Attempting to create image profile '{args.label}' of type '{args.type}'...")
    if args.type == "kiwi":
        profile_path_arg = args.kiwi_path
        # Pass the string directly as per your requirement.
        # IMPORTANT: This directly contradicts the official SUSE Manager API documentation
        # for `image.profile.create` which states `kiwiOptions` should be a `dict`.
        # This implementation assumes your specific SUSE Manager environment
        # expects a raw string here.
        final_kiwi_options_param = args.kiwi_options

        if not args.kiwi_options:
            smt.log_warning("Warning: KIWI profile type selected, but no 'kiwi-options' string provided. An empty string will be used.")
    elif args.type == "kvm":
        profile_path_arg = ""
        # For non-KIWI types, the API *still* might expect a dict or None.
        # Passing a string here could cause issues if the API is strict.
        # Setting to None as a safer default if no KIWI options are relevant.
        final_kiwi_options_param = None
        if args.kiwi_options:
            smt.log_warning("Warning: 'kiwi-options' were provided for a non-KIWI profile type (KVM) and will be ignored (passing None).")
    else:
        profile_path_arg = ""
        final_kiwi_options_param = None # Generic default

    # Calling the image.profile.create API method with individual parameters
    profile_id = smt.image_profile_create(args.label, args.type, args.store_label, profile_path_arg,
                                          args.activation_key, final_kiwi_options_param)

    print(f"Image profile '{args.label}' created successfully with ID: {profile_id}")
    return True

def main():
    """
    Main function for creating image profiles.
    :return: 0 on success, 1 on failure.
    """
    global smt
    parser = argparse.ArgumentParser(
        description="Create a new image profile in SUSE Manager via API. \n"
                    "Connection parameters (server, user, password) are read from configsm.yaml. \n"
                    "Usage: \n create_image_profile.py ",
        formatter_class=argparse.RawTextHelpFormatter # For better multi-line help messages
    )
    # Image Profile Details Arguments (read from command line)
    parser.add_argument('-l', '--label', required=True,
                        help='The label for the new image profile.')
    parser.add_argument('-d', '--description', default="Image profile created via script.",
                        help='A description for the new image profile.')
    parser.add_argument('-t', '--type', default="kvm", choices=["kvm", "xen", "physical", "docker", "kiwi"],
                        help='The type of the image profile (e.g., kvm, kiwi). Default is "kvm".')
    parser.add_argument('-s', '--store-label', required=True,
                        help='The label of the software channel store (e.g., "sles15-sp5-pool-x86_64" or "os_image").')
    parser.add_argument('-a', '--activation-key', required=True,
                        help='The label or ID of the activation key.')
    parser.add_argument('-p', '--kiwi-path', default="",
                        help='Path to the KIWI XML definition file (only for type="kiwi").')
    parser.add_argument('-o', '--kiwi-options', type=str, default="",
                        help='KIWI-specific build options as a single string. '
                             'Example: "--profile x86-self_install --debug"')
    args = parser.parse_args()

    smt = smtools.SMTools("create_software_project")
    # login to suse manager
    smt.log_info("Start")
    smt.suman_login()
    if create_image_profile(args):
        smt.close_program()
    else:
        smt.close_program(1)

if __name__ == "__main__":
    SystemExit(main())
