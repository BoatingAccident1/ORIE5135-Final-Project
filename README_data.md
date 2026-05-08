# ORIE 5135 Project — Data Package

## Instance Format

Each instance is provided in two formats (identical data):

### JSON format (`instance_XX.json`)
```json
{
  "m": 75,           // number of exams
  "n": 75,           // number of available time slots (= m, upper bound)
  "R": 25,           // proctor budget per time slot
  "r": [3, 5, ...],  // proctor requirement for each exam (1-indexed: r[0] = r_1)
  "edges": [[1, 3], [2, 5], ...]  // conflict graph edges (1-indexed)
}
```

### CSV format (two files per instance)
- `instance_XX_params.csv`: contains m, n, R and the proctor requirement for each exam
- `instance_XX_edges.csv`: contains the conflict graph edge list

## Dataset 1 (10 instances)

Use with **all three formulations** (F1: natural, F2: clique-strengthened, F3: extended).

**Time limit: 120 seconds (wall-clock time as reported by the solver).**

| Instances | Size (m) | Description |
|-----------|----------|-------------|
| 01–03     | 35–40    | Small       |
| 04–07     | 60–68    | Medium      |
| 08–10     | 75       | Large       |

## Dataset 2 (9 instances)

Use with **F1 and F2 only** (the extended formulation F3 is not practical at these sizes).

**Time limit: 300 seconds (wall-clock time as reported by the solver).**

| Instances | Size (m) | Description |
|-----------|----------|-------------|
| 01–03     | 80–83    | Small        |
| 04–06     | 87       | Medium       |
| 07–09     | 82–90    | Large        |
