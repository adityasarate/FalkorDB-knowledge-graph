source_url: https://github.com/python/peps.git

git -C data/peps log -1 --format=%cd --date=short 
output: (2026-10-14)

python -c "import glob;print(len(glob.glob('data/peps/peps/pep-*.rst'))+len(glob.glob('data/peps/peps/pep-*/index.rst')))"
output: 744

