#!/usr/bin/python3.5
from __future__ import print_function
from pprint import pprint
from os import path
import sys
import json
import psutil


OVMF_CODE_PATH = path.abspath("./OVMF/OVMF_CODE-pure-efi.fd")

def called_by_qmsh():
    me = psutil.Process()
    parent = psutil.Process(me.ppid())
    grandparent = psutil.Process(parent.ppid())
    called_from_qm = False
    for arg in grandparent.cmdline():
        if "qemu_manager.sh" in arg:
            called_from_qm = True
    return called_from_qm


def eprint(*args, **kwargs):
    args = (" \033[93m*\033[39m",) + args
    print(*args, file=sys.stderr, **kwargs)


def parse_vm(name):
    vm_path = path.join(path.abspath("./VM"), name)
    with open(path.join(vm_path, 'vm.json')) as data_file:
        vm_config = json.load(data_file)
    vm_config["vm_path"] = vm_path
    return vm_config


def start_vm(vm_path=None, kvm=True, uefi=None, virtio=True,
             mem=4086, cores=4, cpu="host", cpu_args=None,
             vga=None, sound=None,
             hdd=None, ide=None, scsi=None):

    if vm_path is None:
        exit("ERROR: No VM path passed")

    if hdd is None:
        hdd = []
    if ide is None:
        ide = []
    if scsi is None:
        scsi = []

    additional_options = "-nodefaults -nodefconfig -net nic,model=virtio -net vde"
    cmdline = "qemu-system-x86_64 "
    drive_id = 0

    # Enable KVM
    cmdline += "-enable-kvm " if kvm else ""

    # ------- Base hardware -------

    # Set the RAM allocation
    cmdline += "-m " + str(mem) + " "

    # Set the CPU options
    cmdline += "-cpu " + (cpu + "," + cpu_args if cpu_args else cpu) + " "

    # Set the CPU core/socket counts
    cmdline += "-smp " + str(cores) + ",sockets=1,cores=" + str(cores) + ",threads=1 "

    # Enable UEFI
    if uefi:
        uefi = path.join(vm_path, uefi)
        cmdline += "-drive if=pflash,format=raw,readonly,file=" + OVMF_CODE_PATH + " "
        cmdline += "-drive if=pflash,format=raw,file=" + uefi + " "
        # cmdline += "-debugcon file:debug.log -global isa-debugcon.iobase=0x402 "

        cmdline += "-spice port=5930,disable-ticketing "
        cmdline += "-device virtio-serial "
        cmdline += "-chardev spicevmc,id=vdagent,name=vdagent "
        cmdline += "-device virtserialport,chardev=vdagent,name=com.redhat.spice.0 "
        vga = "qxl"
        eprint("WARNING: Overridden VGA with qxl since UEFI (and therefore the spice server) is enabled!")

    # Set the VGA emulation
    cmdline += "-vga " + (str(vga) + " -usb -usbdevice tablet" if vga else "none") + " "

    # Set the sound device
    if sound:
        cmdline += "-soundhw " + str(sound) + " "

    # ------- Drives -------

    def add_drive(file, d_id, opt=""):
        return "-drive file=" + file + ",id=drive_" + str(d_id) + ",if=none" + ("," + opt + " " if opt != "" else " ")

    if virtio:
        cmdline += "-device virtio-scsi-pci,id=scsi "

    # IDE
    for dvd_image in ide:
        dvd_image = dvd_image.replace("GLOBAL/", path.abspath("./cd_images") + "/", 1)
        cmdline += add_drive(dvd_image, drive_id) + "-device ide-cd,bus=ide." + str(drive_id) + ",drive=drive_"\
                                                                                                + str(drive_id) + " "
        drive_id += 1

    # SCSI
    for dvd_image in scsi:
        dvd_image = dvd_image.replace("GLOBAL/", path.abspath("./cd_images") + "/", 1)
        cmdline += add_drive(dvd_image, drive_id) + "-device scsi-cd,drive=drive_" + str(drive_id) + " "
        drive_id += 1

    # HDD
    for (hdd_file, options) in hdd:
        hdd_file = path.join(vm_path, hdd_file)
        cmdline += add_drive(hdd_file, drive_id, options) + "-device scsi-hd,drive=drive_" + str(drive_id) + " "
        drive_id += 1

    # TODO: Set up VFIO binding
    # print("echo 1 > /sys/module/kvm/parameters/ignore_msrs")
    print(cmdline + additional_options)

# -rtc base=localtime \
# -net user,smb=/home/themegatb/ \
# -net nic,model=virtio


def main():
    if not called_by_qmsh():
        eprint("This script shouldn't be called directly.")
        exit(1)
    vm_config = parse_vm(sys.argv[1])
    vm_config.pop("name", None)  # eprint("Loaded " + vm_config.pop("name"))
    start_vm(**vm_config)


if __name__ == '__main__':
    main()

