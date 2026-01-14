import sys
from tokkit_benchmark.main import main

# rev-29
main(repo=sys.argv[1] if len(sys.argv) > 1 else None)
