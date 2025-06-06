import numpy as np

GRAVITY = np.array([0, -10], dtype=np.float32)
MASS = 20.0

def apply_gravity(p, dt):
    p.velocity += GRAVITY * dt

def SmoothingKernel(radius, d):
    vol = (np.pi * np.power(radius,4))/6
    return np.where(d <= radius, ((radius - d)**2) / vol, 0.0)

def d_SmoothingKernel(radius, d):
    scale = 12 / (np.pi * np.power(radius,4))
    return np.where(d <= radius, (d - radius) * scale, 0.0)

def calc_density(p, particles, radius): #Density at particle p
    density = 0

    for particle in particles:
        d = np.linalg.norm(particle.position - p.position)
        influence = SmoothingKernel(radius, d)
        density += MASS * influence
    return density

def calc_density2(p, positions, radius): #Vectorized
    distances = np.linalg.norm(positions - p.position, axis=1)
    influences = SmoothingKernel(radius, distances)
    return np.sum(MASS*influences) #sum of densities

def calc_density_gradient(p, particles, radius):
    d_density = 0
    for particle in particles:
        d = np.linalg.norm(particle.position - p.position)
        r_particle = (p.position - particle.position)/d
        slope = d_SmoothingKernel(radius, d)
        d_density += MASS * slope * r_particle
    return d_density

def calc_density_gradient2(p, positions, radius): #Vectorized
    distances = np.linalg.norm(positions - p.position, axis=1)
    r_particles = np.where(distances[:, None] > 1e-6, (p.position - positions) / distances[:, None], 0.0)
    slopes = d_SmoothingKernel(radius, distances)
    return np.sum(MASS * slopes[:, None] * r_particles, axis=0)

def calc_shared_pressure(density_A, density_B):
    pressure_A = density_to_pressure(density_A)
    pressure_B = density_to_pressure(density_B)
    return (pressure_A + pressure_B) / 2

def calc_pressure_force(p, particles, radius):
    d_P = 0

    for particle in particles:
        d = np.linalg.norm(particle.position - p.position)
        if d > 1e-5:
            r_particle = (p.position - particle.position)/d
            slope = d_SmoothingKernel(radius, d)
            shared_pressure = calc_shared_pressure(particle.density, p.density)
            if particle.density > 1e-5:
                d_P += shared_pressure * MASS * slope * r_particle / particle.density
    return d_P

def calc_pressure_force2(p, densities, positions, radius):
    distances = np.linalg.norm(positions - p.position, axis=1)
    r_particles = np.where(distances[:, None] > 1e-6, (p.position - positions) / distances[:, None], 0.0)
    slopes = d_SmoothingKernel(radius, distances)
    shared_pressures = calc_shared_pressure(densities, p.density)

    contributions = np.where(
    densities[:, None] > 1e-6,  
    (shared_pressures * MASS * slopes)[:, None] * r_particles / densities[:, None],  # Safe division
    0.0  
    )   

    return np.sum(contributions, axis=0) 

def density_to_pressure(density):
    t_density = 1
    p_multiplier = 10
    e_density = density - t_density
    pressure = e_density * p_multiplier
    return pressure
    
def update_spatial_lookup(points, radius):
    
    pos_array = np.array([p.position for p in points])
    
    cell_coords = pos_to_cell_coord(pos_array, radius)
    cell_keys = get_key_from_hash(hash_cell(cell_coords[:, 0], cell_coords[:, 1]),len(points))

    indices = np.arange(len(points), dtype=np.uint32)
    spatial_lookup = np.stack((indices, cell_keys), axis=1)
    spatial_lookup = spatial_lookup[np.argsort(spatial_lookup[:,1])]

    start_indices = np.full(np.max(cell_keys) + 1, np.iinfo(np.uint32).max, dtype=np.uint32)

    _, first_indices = np.unique(spatial_lookup[:,1], return_index=True)
    unique_keys = spatial_lookup[first_indices, 1]
    start_indices = dict(zip(unique_keys, first_indices))

    return spatial_lookup, start_indices

def pos_to_cell_coord(pos_array, radius):
    return np.floor(pos_array / radius).astype(int)

def hash_cell(cell_x, cell_y):
    return (cell_x * 15823) + (cell_y * 9737333)

def get_key_from_hash(h, length):
    return (h % length)

def for_each_point_within_radius(sample_point, points, radius, spatial_lookup, start_indices):
    centre_x, centre_y = pos_to_cell_coord(sample_point.position, radius)
    neighbours = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            cell_x, cell_y = centre_x + dx, centre_y + dy
            cell_key = get_key_from_hash(hash_cell(cell_x, cell_y), len(points))

            start_index = start_indices.get(cell_key)
            if start_index is None:
                continue #cell empty

            i = start_index
            while i < len(spatial_lookup) and spatial_lookup[i, 1] == cell_key:
                index = spatial_lookup[i, 0]
                other_point = points[index]
                dist = np.linalg.norm(sample_point.position - other_point.position)
                if dist <= radius:
                    neighbours.append(other_point)
                i += 1

    return neighbours #neighbour positions
