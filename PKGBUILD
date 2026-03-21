# Maintainer: UnDadFeated <jscheema@gmail.com>
pkgname=chronoarchiver
pkgver=1.0.9
pkgrel=1
pkgdesc="Unified Media Archive Organizer and AV1 Encoder"
arch=('any')
url="https://github.com/UnDadFeated/ChronoArchiver"
license=('MIT')
depends=(
    'python'
    'python-customtkinter'
    'opencv'
    'python-pillow'
    'python-piexif'
    'python-psutil'
    'python-platformdirs'
    'python-requests'
    'ffmpeg'
)
makedepends=('git' 'python-setuptools')
source=("git+https://github.com/UnDadFeated/ChronoArchiver.git#tag=v${pkgver}")
sha256sums=('SKIP')

package() {
    cd "${srcdir}/ChronoArchiver"
    install -d "${pkgdir}/usr/share/${pkgname}"
    cp -rv src/* "${pkgdir}/usr/share/${pkgname}/"
    
    install -d "${pkgdir}/usr/bin"
    echo -e "#!/bin/bash\nexport PYTHONPATH=\$PYTHONPATH:/usr/share/${pkgname}\npython /usr/share/${pkgname}/ui/app.py \"\$@\"" > "${pkgdir}/usr/bin/${pkgname}"
    chmod +x "${pkgdir}/usr/bin/${pkgname}"
}
