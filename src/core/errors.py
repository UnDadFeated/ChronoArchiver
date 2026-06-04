"""Standardized application-wide error codes database for ChronoArchiver."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


@dataclass(frozen=True)
class ErrorDetail:
    code: str
    area: str
    description: str
    possible_fixes: str


class AppErrorCode(Enum):
    # ==========================================
    # Venv / Setup (E100-E199)
    # ==========================================
    VENV_INTERPRETER_NOT_FOUND = ErrorDetail(
        "E101",
        "Venv / Setup",
        "The host Python interpreter or launcher was not found or lacks virtual environment features.",
        "Ensure Python 3.9–3.14 is installed on your PATH with the 'venv' and 'ensurepip' modules.",
    )
    VENV_CREATION_FAILED = ErrorDetail(
        "E102",
        "Venv / Setup",
        "Creating the Python virtual environment failed.",
        "Check file permissions in the destination directory or run ChronoArchiver setup launcher with administrator/write permissions.",
    )
    VENV_PIP_INSTALL_FAILED = ErrorDetail(
        "E103",
        "Venv / Setup",
        "Installing dependency packages into the venv failed.",
        "Check your internet connection, disk space, or configure your network proxy / pip configuration to allow downloading packages from PyPI.",
    )
    FFMPEG_DOWNLOAD_FAILED = ErrorDetail(
        "E104",
        "Venv / Setup",
        "Downloading or extracting static FFmpeg binaries failed.",
        "Ensure you have a working internet connection and write permissions to the data directory.",
    )
    VENV_PYTHON_VERSION_INCOMPATIBLE = ErrorDetail(
        "E105",
        "Venv / Setup",
        "The current host Python version is incompatible with the virtual environment requirements.",
        "Use a Python version between 3.9 and 3.14 inclusive.",
    )
    VENV_BROKEN_EXECUTABLE = ErrorDetail(
        "E106",
        "Venv / Setup",
        "The Python interpreter inside the virtual environment is broken or cannot be executed.",
        "Run 'python src/bootstrap.py --reset-venv' to recreate the virtual environment from scratch.",
    )
    VENV_MISSING_TKINTER = ErrorDetail(
        "E107",
        "Venv / Setup",
        "The tkinter GUI package is missing on the host Python interpreter.",
        "Install python3-tk or ensure tkinter is selected in your Python Windows installation options.",
    )
    VENV_UPGRADE_PIP_FAILED = ErrorDetail(
        "E108",
        "Venv / Setup",
        "Upgrading pip within the virtual environment failed.",
        "Check permissions or configure pip proxy settings if behind a corporate firewall.",
    )

    # ==========================================
    # Media Organizer (E200-E299)
    # ==========================================
    ORGANIZER_SRC_NOT_FOUND = ErrorDetail(
        "E201",
        "Media Organizer",
        "The selected source directory does not exist.",
        "Double check the path and make sure the directory or external drive is connected and mounted.",
    )
    ORGANIZER_SRC_NOT_WRITABLE = ErrorDetail(
        "E202",
        "Media Organizer",
        "The source directory is not writable (needed for in-place organization).",
        "Check permissions of the folder or run ChronoArchiver with permissions to write to this path.",
    )
    ORGANIZER_TGT_NOT_WRITABLE = ErrorDetail(
        "E203",
        "Media Organizer",
        "The target directory is not writable.",
        "Ensure you have write permission to the output path or try selecting a different target directory.",
    )
    ORGANIZER_PATHS_OVERLAP = ErrorDetail(
        "E204",
        "Media Organizer",
        "The source and target directories overlap or are identical.",
        "Ensure target is not inside source (or vice-versa), or run in-place mode by clearing the target path.",
    )
    ORGANIZER_RESOLUTION_FAILED = ErrorDetail(
        "E205",
        "Media Organizer",
        "Failed to safely resolve directory paths (path traversal risk detected).",
        "Ensure the directory paths do not contain invalid directory traversal sequences (e.g. '..').",
    )
    ORGANIZER_EXIF_READ_FAILED = ErrorDetail(
        "E206",
        "Media Organizer",
        "Failed to read EXIF metadata from the image file.",
        "Ensure the file is not corrupted and is a supported raster image (JPEG, PNG, WEBP, TIFF).",
    )
    ORGANIZER_EXIF_WRITE_FAILED = ErrorDetail(
        "E207",
        "Media Organizer",
        "Failed to write rotated EXIF metadata back to the image file.",
        "Verify write permissions on the file and check if another application is holding a file lock.",
    )
    ORGANIZER_DISK_SPACE_LOW = ErrorDetail(
        "E208",
        "Media Organizer",
        "Insufficient disk space on target partition to complete organization.",
        "Free up space on the destination drive or select a target partition with more available space.",
    )
    ORGANIZER_FILE_MOVE_FAILED = ErrorDetail(
        "E209",
        "Media Organizer",
        "Failed to move or copy the media file to the destination folder.",
        "Check for file locks, file size limitations on the target filesystem (e.g., FAT32's 4GB limit), or target path length limits.",
    )
    ORGANIZER_SYMLINK_FAILED = ErrorDetail(
        "E210",
        "Media Organizer",
        "Failed to create symbolic link to the media file.",
        "On Windows, ensure ChronoArchiver is run as administrator or Developer Mode is enabled in Windows settings to allow symlinks.",
    )
    ORGANIZER_FILE_CORRUPT = ErrorDetail(
        "E211",
        "Media Organizer",
        "The media file appears corrupt and cannot be read.",
        "Verify if the file can be opened in native OS players or viewing applications.",
    )

    # ==========================================
    # Mass Video Encoder (E300-E399)
    # ==========================================
    ENCODER_FFMPEG_MISSING = ErrorDetail(
        "E301",
        "Mass Video Encoder",
        "FFmpeg or ffprobe binaries are missing or failed to run.",
        "Ensure setup completed successfully or run 'python src/bootstrap.py --reset-venv' to re-initialize dependencies.",
    )
    ENCODER_INPUT_INVALID = ErrorDetail(
        "E302",
        "Mass Video Encoder",
        "The input video file is invalid, empty, or has no readable video stream.",
        "Verify the video file plays locally, is not corrupted, and contains a valid video stream.",
    )
    ENCODER_CRASHED = ErrorDetail(
        "E303",
        "Mass Video Encoder",
        "The FFmpeg process crashed or exited unexpectedly.",
        "Check the encoder log lines for specific errors, or try software encoding if hardware acceleration fails.",
    )
    ENCODER_ACCEL_UNSUPPORTED = ErrorDetail(
        "E304",
        "Mass Video Encoder",
        "The requested hardware encoder (NVENC, AMF, QSV, VAAPI) is not supported by your GPU/driver.",
        "Upgrade your graphics drivers or switch to software encoding (SVT-AV1, x264, x265) in the settings.",
    )
    ENCODER_PASSTHROUGH_FAILED = ErrorDetail(
        "E305",
        "Mass Video Encoder",
        "The stream copy passthrough failed for this video.",
        "Try re-encoding the file with the software encoder instead of stream-copy remuxing.",
    )
    ENCODER_PROBE_TIMEOUT = ErrorDetail(
        "E306",
        "Mass Video Encoder",
        "Probing the video duration or stream metadata timed out.",
        "Verify if the video is located on a slow network share or has bad indices; try remuxing it locally.",
    )
    ENCODER_OUTPUT_NOT_WRITABLE = ErrorDetail(
        "E307",
        "Mass Video Encoder",
        "The output file path is not writable.",
        "Ensure the output directory exists and is writable, and check that the destination file is not currently locked.",
    )
    ENCODER_AUDIO_FAILED = ErrorDetail(
        "E308",
        "Mass Video Encoder",
        "Encoding the audio stream failed.",
        "Verify if the source audio track is corrupt, or choose a different audio codec (e.g. AAC).",
    )

    # ==========================================
    # SSH / Remote (E400-E499)
    # ==========================================
    SSH_CONNECTION_FAILED = ErrorDetail(
        "E401",
        "SSH / Remote",
        "SSH connection test failed or timed out.",
        "Check the host address, port, username, password/keys, and ensure the target machine's SSH daemon is active.",
    )
    SSH_SSHPASS_MISSING = ErrorDetail(
        "E402",
        "SSH / Remote",
        "The 'sshpass' utility is not installed on the system (required for password-based SSH).",
        "Install 'sshpass' using your package manager, or configure SSH public keys for key-based authentication.",
    )
    SSH_AUTH_FAILED = ErrorDetail(
        "E403",
        "SSH / Remote",
        "SSH authentication failed (invalid username, password, or key).",
        "Verify your remote login credentials or public SSH keys configuration on the remote host.",
    )
    SSH_REMOTE_CMD_FAILED = ErrorDetail(
        "E404",
        "SSH / Remote",
        "The command executed on the remote host returned a non-zero exit status.",
        "Check the remote server log and permissions for the command you are attempting to run.",
    )
    SSH_SFTP_UPLOAD_FAILED = ErrorDetail(
        "E405",
        "SSH / Remote",
        "SFTP upload or download of media files failed.",
        "Check storage space on the remote host, remote directory permissions, and network stability.",
    )
    SSH_HOST_UNREACHABLE = ErrorDetail(
        "E406",
        "SSH / Remote",
        "The remote host is unreachable on the network.",
        "Ping the target server, check your network configuration, and make sure any firewalls allow port 22 traffic.",
    )

    # ==========================================
    # AI Media Scanner (E500-E599)
    # ==========================================
    SCANNER_OPENCV_MISSING = ErrorDetail(
        "E501",
        "AI Media Scanner",
        "The OpenCV library is missing in the current virtual environment.",
        "Open the AI Media Scanner panel and follow the prompts to install the appropriate OpenCV binary package.",
    )
    SCANNER_MODEL_LOAD_FAILED = ErrorDetail(
        "E502",
        "AI Media Scanner",
        "Failed to load the AI classification model (ONNX Runtime).",
        "Ensure the model file has been fully downloaded and is not corrupted, or click 'Re-download models' in the settings.",
    )
    SCANNER_CUDA_OOM = ErrorDetail(
        "E503",
        "AI Media Scanner",
        "CUDA Out of Memory occurred during AI media scanning.",
        "Lower the batch size in the settings, close other GPU-intensive applications, or use CPU execution mode.",
    )
    SCANNER_FRAME_READ_FAILED = ErrorDetail(
        "E504",
        "AI Media Scanner",
        "Failed to read or decode video frames from the input video file.",
        "Ensure the video file is not corrupted and its codec is supported by your OpenCV/FFmpeg installation.",
    )
    SCANNER_RUNTIME_ERROR = ErrorDetail(
        "E505",
        "AI Media Scanner",
        "An unexpected error occurred during the inference loop.",
        "Check the session debug logs for traceback detail and report the bug if reproducible.",
    )

    # ==========================================
    # AI Image Upscaler (E600-E699)
    # ==========================================
    IMAGE_UPSCALER_TORCH_MISSING = ErrorDetail(
        "E601",
        "AI Image Upscaler",
        "PyTorch library is missing in the current virtual environment.",
        "Use the installer dialog in the AI Image Upscaler panel to set up PyTorch.",
    )
    IMAGE_UPSCALER_MODEL_LOAD_FAILED = ErrorDetail(
        "E602",
        "AI Image Upscaler",
        "Failed to load the RealESRGAN model weight weights.",
        "Verify your internet connection to download the weights, or check write permissions in the 'models/' directory.",
    )
    IMAGE_UPSCALER_CUDA_OOM = ErrorDetail(
        "E603",
        "AI Image Upscaler",
        "GPU Out of Memory (CUDA OOM) occurred during image upscaling.",
        "Reduce the scale factor, enable tile mode if available, or switch the upscaler runtime to CPU.",
    )
    IMAGE_UPSCALER_SAVE_FAILED = ErrorDetail(
        "E604",
        "AI Image Upscaler",
        "Failed to save the upscaled image file.",
        "Verify that you have write permissions to the destination folder and the disk is not full.",
    )

    # ==========================================
    # AI Video Upscaler (E700-E799)
    # ==========================================
    VIDEO_UPSCALER_TORCH_MISSING = ErrorDetail(
        "E701",
        "AI Video Upscaler",
        "PyTorch library is missing or invalid in the current virtual environment.",
        "Launch the AI Video Upscaler panel installer to configure PyTorch dependencies.",
    )
    VIDEO_UPSCALER_CUDA_OOM = ErrorDetail(
        "E702",
        "AI Video Upscaler",
        "GPU Out of Memory (CUDA OOM) during video upscaling inference.",
        "Switch to a lower resolution model, enable tiling, or run the job using CPU mode.",
    )
    VIDEO_UPSCALER_MUX_FAILED = ErrorDetail(
        "E703",
        "AI Video Upscaler",
        "Failed to mux upscaled frames and source audio back into the final video file.",
        "Ensure FFmpeg is installed and check your temporary storage directory permissions.",
    )
    VIDEO_UPSCALER_PROCESS_CRASHED = ErrorDetail(
        "E704",
        "AI Video Upscaler",
        "The video upscaler subprocess crashed or was terminated.",
        "Check log details in the console for Out-of-Memory warnings or system process termination codes.",
    )

    # ==========================================
    # Model Management / Download (E800-E899)
    # ==========================================
    MODEL_DOWNLOAD_TIMEOUT = ErrorDetail(
        "E801",
        "Model Manager",
        "The model download connection timed out.",
        "Verify network speed and retry, or download the model manually and place it in the application's models folder.",
    )
    MODEL_HASH_MISMATCH = ErrorDetail(
        "E802",
        "Model Manager",
        "The downloaded model file failed the integrity hash check (MD5/SHA256).",
        "Delete the partially downloaded file and try downloading the model again.",
    )
    MODEL_EXTRACT_FAILED = ErrorDetail(
        "E803",
        "Model Manager",
        "Extracting model archive weights failed.",
        "Check permissions or free disk space, and ensure the archive tool has access to the temporary directory.",
    )

    # ==========================================
    # Network, OS, & System (E900-E999)
    # ==========================================
    SYSTEM_OS_UNSUPPORTED = ErrorDetail(
        "E901",
        "System / OS",
        "This platform or OS architecture is not supported.",
        "Ensure you are running on a 64-bit Windows or Linux operating system.",
    )
    SYSTEM_NO_INTERNET = ErrorDetail(
        "E902",
        "System / OS",
        "No active internet connection was detected (required for download actions).",
        "Check your network cables, Wi-Fi status, or proxy configuration.",
    )
    SYSTEM_DISK_READ_ONLY = ErrorDetail(
        "E903",
        "System / OS",
        "The filesystem is read-only.",
        "Mount the drive in read-write mode or select a different folder on your local storage.",
    )


def format_error_msg(code: AppErrorCode, context: Optional[str] = None) -> str:
    detail = code.value
    msg = f"ERROR: [{detail.code}] {detail.area} — {detail.description}"
    if context:
        msg += f" (Context: {context})"
    msg += f"\n  Possible Fix: {detail.possible_fixes}"
    return msg
