Content-Type: multipart/mixed; boundary="===============0720507736290932298=="
MIME-Version: 1.0
Number-Attachments: 1

--===============0720507736290932298==
MIME-Version: 1.0
Content-Type: text/cloud-config
Content-Disposition: attachment; filename="part-001"

#cloud-config
growpart:
  mode: 'off'
preserve_hostname: true
resize_rootfs: false
ssh_pwauth: true
users:
- lock_passwd: false
  name: pinball
write_files:
- content: "Disabled by Ubuntu live installer after first boot.\nTo re-enable cloud-init\
    \ on this image run:\n  sudo cloud-init clean --machine-id\n"
  defer: true
  path: /etc/cloud/cloud-init.disabled

--===============0720507736290932298==--
