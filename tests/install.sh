set -e

# Python dependencies
pip install flake8 json-merge-patch jsonschema pytest requests rfc3987 strict-rfc3339

# Ruby dependencies
curl -s -S -o /tmp/Gemfile $BASEDIR/fixtures/Gemfile
# Use same magic incantation as https://github.com/rails/rails/blob/288fbc7ff47b6aae0d5bab978ae16858a425f643/.travis.yml#L30-L31
gem update --system
gem install bundler -v 1.15.4
bundle _1.15.4_ install --gemfile=/tmp/Gemfile --path /tmp/vendor/bundle --binstubs=/tmp/bin
