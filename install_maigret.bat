@echo off
echo ==============================================
echo 1. VS 2022 Build Tools Ayarlari Yuklenir...
echo ==============================================
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

echo.
echo ==============================================
echo 2. Rust/Cargo PATH-a elave edilir...
echo ==============================================
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
cargo --version

echo.
echo ==============================================
echo 3. Python bidi ve Maigret qurasdirilir...
echo ==============================================
C:\Users\Administrator\Desktop\SCOSINT_AI\.venv\Scripts\python.exe -m pip install python-bidi maigret

echo.
echo ==============================================
echo BITDI.
echo ==============================================
