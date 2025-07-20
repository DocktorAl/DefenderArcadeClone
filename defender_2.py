import pygame
import random
import sys
import math
import numpy as np

# --- Initialization ---
pygame.init()
pygame.mixer.init()

# --- Screen and World Variables ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Defender")

# The game world is wider than the screen to allow for scrolling
WORLD_WIDTH = SCREEN_WIDTH * 4
GROUND_LEVEL = SCREEN_HEIGHT - 60
PLAYABLE_HEIGHT = GROUND_LEVEL - 60 # Height from scanner to ground
FALL_DAMAGE_DISTANCE = PLAYABLE_HEIGHT * 0.2 # 20% of playable height

# --- Game Clock ---
clock = pygame.time.Clock()
FPS = 60

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
GREY = (192, 192, 192)
LIGHT_GREY = (160, 160, 160)

# --- Fonts ---
font = pygame.font.SysFont("Consolas", 18, bold=True)

# --- Sound Effects ---
def create_sound(freq, duration_ms):
    sample_rate = pygame.mixer.get_init()[0]
    max_amp = 2**(abs(pygame.mixer.get_init()[1]) - 1) - 1
    duration_samples = int(duration_ms * sample_rate / 1000)
    
    samples = [max_amp * math.sin(2 * math.pi * freq * i / sample_rate) for i in range(duration_samples)]
    mono_array = np.array(samples, dtype=np.int16)
    stereo_array = np.column_stack([mono_array, mono_array])
    
    sound = pygame.sndarray.make_sound(stereo_array)
    sound.set_volume(0.1)
    return sound

laser_sound = create_sound(440, 100)
explosion_sound = create_sound(220, 400)
rescue_sound = create_sound(880, 200)
humanoid_death_sound = create_sound(150, 500)

# --- Star Background ---
class Star:
    def __init__(self):
        self.world_x = random.randint(0, WORLD_WIDTH)
        self.world_y = random.randint(50, SCREEN_HEIGHT - 100)
        self.brightness = random.randint(50, 255)
        self.twinkle_speed = random.uniform(0.02, 0.05)
        self.twinkle_offset = random.uniform(0, 2 * math.pi)
    
    def update(self):
        # Simple twinkling effect
        self.brightness = int(128 + 127 * math.sin(pygame.time.get_ticks() * self.twinkle_speed + self.twinkle_offset))
        self.brightness = max(50, min(255, self.brightness))
    
    def draw(self, screen, camera_x):
        screen_x = self.world_x - camera_x
        if -5 <= screen_x <= SCREEN_WIDTH + 5:
            color = (self.brightness, self.brightness, self.brightness)
            pygame.draw.circle(screen, color, (int(screen_x), int(self.world_y)), 1)

# Create starfield
stars = [Star() for _ in range(150)]

# --- Game Classes ---
class Particle(pygame.sprite.Sprite):
    """A single particle for the explosion effect."""
    def __init__(self, x, y, color):
        super().__init__()
        self.world_x = x
        self.world_y = y
        self.color = color
        self.velocity_x = random.uniform(-4, 4)
        self.velocity_y = random.uniform(-4, 4)
        self.lifespan = random.randint(20, 40) # Frames
        self.initial_lifespan = self.lifespan
        
        self.size = random.randint(2, 5)
        self.image = pygame.Surface((self.size, self.size))
        self.image.fill(self.color)
        self.rect = self.image.get_rect(center=(self.world_x, self.world_y))

    def update(self):
        self.world_x += self.velocity_x
        self.world_y += self.velocity_y
        self.lifespan -= 1

        # Fade effect by reducing alpha
        alpha = int(255 * (self.lifespan / self.initial_lifespan))
        self.image.set_alpha(alpha)

        if self.lifespan <= 0:
            self.kill()

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        # Longer, more triangular ship sprite
        self.image_orig = pygame.Surface((32, 10), pygame.SRCALPHA)
        
        # Engine (Red)
        pygame.draw.rect(self.image_orig, RED, (0, 2, 6, 6)) 
        
        # Main Body (Grey)
        pygame.draw.rect(self.image_orig, GREY, (6, 4, 22, 2))  # Central spine
        pygame.draw.rect(self.image_orig, GREY, (8, 2, 16, 6))  # Thicker part of the body
        pygame.draw.rect(self.image_orig, GREY, (24, 3, 4, 4)) # Tapering section
        
        # Nose Tip (Green)
        pygame.draw.rect(self.image_orig, GREEN, (28, 4, 4, 2))
        
        self.image = self.image_orig.copy()
        self.rect = self.image.get_rect()
        self.world_x = WORLD_WIDTH / 2
        self.world_y = SCREEN_HEIGHT / 2
        self.velocity_x = 0
        self.velocity_y = 0
        self.lives = 3
        self.bombs = 3
        self.facing_right = True
        self.carried_humanoid = None # Humanoid being carried
        self.invincible = False
        self.invincible_timer = 0
        
        # Create flipped image for left movement
        self.image_right = self.image_orig.copy()
        self.image_left = pygame.transform.flip(self.image_orig, True, False)

    def update(self):
        # Handle invincibility
        if self.invincible:
            self.invincible_timer -= 1
            # Blinking effect - slowed down
            if self.invincible_timer % 20 < 10:
                self.image.set_alpha(0)
            else:
                self.image.set_alpha(255)
            if self.invincible_timer <= 0:
                self.invincible = False
                self.image.set_alpha(255)
        
        keys = pygame.key.get_pressed()
        
        # Momentum-based movement (more like original)
        acceleration = 0.8
        max_speed = 8
        friction = 0.97 # CHANGE: Increased friction for more glide
        
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.velocity_x -= acceleration
            self.facing_right = False
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.velocity_x += acceleration
            self.facing_right = True
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.velocity_y -= acceleration
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.velocity_y += acceleration
        
        # Apply friction
        self.velocity_x *= friction
        self.velocity_y *= friction
        
        # Limit max speed
        self.velocity_x = max(-max_speed, min(max_speed, self.velocity_x))
        self.velocity_y = max(-max_speed, min(max_speed, self.velocity_y))
        
        # Update position
        self.world_x += self.velocity_x
        self.world_y += self.velocity_y
        
        # World wrapping for X
        if self.world_x < 0:
            self.world_x = WORLD_WIDTH
        if self.world_x > WORLD_WIDTH:
            self.world_x = 0
            
        # Screen boundaries for Y
        current_ground_y = get_terrain_height_at(self.world_x)
        if self.world_y < 60:  # Scanner area
            self.world_y = 60
            self.velocity_y = 0
        if self.world_y > current_ground_y - 10:  # Variable ground level
            self.world_y = current_ground_y - 10
            self.velocity_y = 0
        
        # Update sprite image based on direction
        base_image = self.image_right if self.facing_right else self.image_left
        self.image = base_image.copy()

    def shoot(self):
        # Shoot in facing direction
        direction = 1 if self.facing_right else -1
        laser = Laser(self.world_x, self.world_y, direction)
        all_sprites.add(laser)
        lasers.add(laser)
        laser_sound.play()

    def respawn(self):
        self.world_x = camera_x + SCREEN_WIDTH / 2
        self.world_y = SCREEN_HEIGHT / 2
        self.velocity_x = 0
        self.velocity_y = 0
        self.invincible = True
        self.invincible_timer = 120 # 2 seconds at 60 FPS

class Laser(pygame.sprite.Sprite):
    def __init__(self, x, y, direction=1):
        super().__init__()
        self.image = pygame.Surface((15, 3))
        self.image.fill(CYAN)
        self.rect = self.image.get_rect()
        self.world_x = x
        self.world_y = y
        self.speed_x = 15 * direction
        self.direction = direction

    def update(self):
        self.world_x += self.speed_x
        
        # Remove laser if it goes off-world
        if self.world_x < -100 or self.world_x > WORLD_WIDTH + 100:
            self.kill()

class Lander(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        # Authentic pixel-art style Lander
        self.image = pygame.Surface((16, 14), pygame.SRCALPHA)
        # Main body (green)
        pygame.draw.rect(self.image, GREEN, (2, 0, 12, 2))
        pygame.draw.rect(self.image, GREEN, (0, 2, 16, 10))
        pygame.draw.rect(self.image, GREEN, (2, 12, 12, 2))
        # Cockpit (red)
        pygame.draw.rect(self.image, RED, (6, 4, 4, 6))
        # Thrusters (yellow)
        pygame.draw.rect(self.image, YELLOW, (0, 6, 2, 2))
        pygame.draw.rect(self.image, YELLOW, (14, 6, 2, 2))
        # Top detail (blue)
        pygame.draw.rect(self.image, BLUE, (6, 0, 4, 2))
        
        self.rect = self.image.get_rect()
        self.world_x = random.randint(0, WORLD_WIDTH)
        self.world_y = random.randint(80, 200)
        self.velocity_x = random.uniform(-2, 2)
        self.velocity_y = random.uniform(0.5, 1.5)
        self.target_humanoid = None
        self.has_humanoid = False

    def update(self):
        # STATE 1: ASCENDING (highest priority)
        if self.has_humanoid:
            if self.target_humanoid and self.target_humanoid.alive():
                self.world_y -= 2
                self.target_humanoid.world_x = self.world_x
                self.target_humanoid.world_y = self.world_y + 25
                if self.world_y < 0:  # Escaped to top
                    # CHANGE: Spawn a Mutant
                    mutant = Mutant(self.world_x, self.world_y)
                    all_sprites.add(mutant)
                    enemies.add(mutant)
                    self.target_humanoid.kill()
                    self.kill()
            else: # Target was killed
                self.has_humanoid = False
                self.target_humanoid = None
            return

        # STATE 2: FIND A TARGET (if we don't have one)
        if self.target_humanoid is None or not self.target_humanoid.alive() or self.target_humanoid.is_abducted:
            self.target_humanoid = None
            available_humanoids = [h for h in humanoids.sprites() if not h.is_abducted]
            if available_humanoids:
                # Find the closest humanoid
                self.target_humanoid = min(available_humanoids, key=lambda h: math.hypot(h.world_x - self.world_x, h.world_y - self.world_y))
        
        # STATE 3: ACT (PURSUE or WANDER)
        if self.target_humanoid:
            # Pursue target
            dx = self.target_humanoid.world_x - self.world_x
            dy = self.target_humanoid.world_y - self.world_y
            
            # CHANGE: Increased pursuit speed
            if abs(dx) > 5:
                self.world_x += 2.5 if dx > 0 else -2.5
            if abs(dy) > 5:
                self.world_y += 2.0 if dy > 0 else -2.0
            
            # Check for successful abduction
            if abs(dx) < 15 and abs(dy) < 15:
                self.has_humanoid = True
                self.target_humanoid.is_abducted = True
        else:
            # No valid target, so wander randomly
            self.world_x += self.velocity_x
            self.world_y += self.velocity_y
            
            # Bounce off side and top boundaries, but not ground
            if self.world_x <= 0 or self.world_x >= WORLD_WIDTH:
                self.velocity_x *= -1
            if self.world_y <= 80:
                self.velocity_y = abs(self.velocity_y)

class Mutant(pygame.sprite.Sprite):
    """A fast, aggressive enemy that hunts the player."""
    def __init__(self, x, y):
        super().__init__()
        # Authentic pixel-art style Mutant
        self.image = pygame.Surface((16, 8), pygame.SRCALPHA)
        pygame.draw.rect(self.image, ORANGE, (0, 2, 16, 4))
        pygame.draw.rect(self.image, ORANGE, (2, 0, 12, 8))
        pygame.draw.rect(self.image, RED, (6, 2, 4, 4))
        
        self.rect = self.image.get_rect(center=(x, y))
        self.world_x = x
        self.world_y = y
        self.speed = 4

    def update(self):
        # Simple homing behavior
        dx = player.world_x - self.world_x
        dy = player.world_y - self.world_y
        dist = math.hypot(dx, dy)
        
        if dist > 0:
            # Move towards player
            self.world_x += (dx / dist) * self.speed
            self.world_y += (dy / dist) * self.speed

        # World wrapping
        if self.world_x < 0: self.world_x = WORLD_WIDTH
        if self.world_x > WORLD_WIDTH: self.world_x = 0
        if self.world_y < 0: self.world_y = SCREEN_HEIGHT
        if self.world_y > SCREEN_HEIGHT: self.world_y = 0

class Humanoid(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        # Authentic pixel-art style Humanoid
        self.image = pygame.Surface((8, 14), pygame.SRCALPHA)
        # Body
        pygame.draw.rect(self.image, WHITE, (2, 0, 4, 12))
        # Arms
        pygame.draw.rect(self.image, WHITE, (0, 2, 8, 2))
        # Legs
        pygame.draw.rect(self.image, WHITE, (2, 12, 2, 2))
        pygame.draw.rect(self.image, WHITE, (4, 12, 2, 2))
        
        self.rect = self.image.get_rect()
        self.world_x = random.randint(50, WORLD_WIDTH - 50)
        self.world_y = get_terrain_height_at(self.world_x) - 7 # Spawn on variable terrain
        self.velocity_y = 0
        self.is_abducted = False
        self.is_falling = False
        self.is_carried = False
        self.is_dead = False
        self.death_timer = 0
        self.fall_start_y = 0

    def update(self):
        if self.is_carried:
            # Stick to the player
            self.world_x = player.world_x
            self.world_y = player.world_y + 20 # Position below the player
            return

        if self.is_falling:
            self.velocity_y += 0.02
            self.world_y += self.velocity_y
            
            # Hit ground
            current_ground_y = get_terrain_height_at(self.world_x)
            if self.world_y >= current_ground_y - 7:
                self.world_y = current_ground_y - 7
                self.is_falling = False
                self.velocity_y = 0

                fall_distance = self.world_y - self.fall_start_y
                if fall_distance > FALL_DAMAGE_DISTANCE:
                    # Die from long fall
                    self.is_dead = True
                    self.image.fill(RED)
                    humanoid_death_sound.play()
                else:
                    # Survived short fall
                    pass # Just lands safely
        
        if self.is_dead:
            self.death_timer += 1
            if self.death_timer > 60: # 1 second at 60 FPS
                self.kill()

# --- Helper Functions ---
def create_explosion(x, y, color):
    """Creates a burst of particles at a given location."""
    for _ in range(15):
        particle = Particle(x, y, color)
        all_sprites.add(particle)
        particles.add(particle)

def get_terrain_height_at(x):
    """Calculates the y-coordinate of the terrain at a given x-coordinate."""
    # Find which two terrain points the x-coordinate is between
    for i in range(len(terrain_points) - 1):
        p1 = terrain_points[i]
        p2 = terrain_points[i+1]
        if p1[0] <= x < p2[0]:
            # Linear interpolation to find the exact height
            y = p1[1] + (x - p1[0]) * (p2[1] - p1[1]) / (p2[0] - p1[0])
            return y
    return GROUND_LEVEL # Fallback for edges

def draw_terrain():
    # Draw terrain features
    for i in range(len(terrain_points) - 1):
        p1_world = terrain_points[i]
        p2_world = terrain_points[i+1]
        p1_screen = (p1_world[0] - camera_x, p1_world[1])
        p2_screen = (p2_world[0] - camera_x, p2_world[1])
        
        # Only draw lines that are on screen
        if max(p1_screen[0], p2_screen[0]) >= 0 and min(p1_screen[0], p2_screen[0]) <= SCREEN_WIDTH:
            pygame.draw.line(screen, GREEN, p1_screen, p2_screen, 2)

def draw_scanner():
    # Scanner background
    pygame.draw.rect(screen, BLACK, (0, 0, SCREEN_WIDTH, 50))
    pygame.draw.rect(screen, GREEN, (0, 0, SCREEN_WIDTH, 50), 2)
    
    # Scanner grid
    for i in range(0, SCREEN_WIDTH, 100):
        pygame.draw.line(screen, (0, 100, 0), (i, 0), (i, 50))
    
    # Scanner drawing constants
    SCANNER_TOP_Y = 10
    SCANNER_BOTTOM_Y = 45
    SCANNER_DISPLAY_HEIGHT = SCANNER_BOTTOM_Y - SCANNER_TOP_Y
    
    # Draw entities on scanner
    scale = SCREEN_WIDTH / WORLD_WIDTH
    
    # Enemies (red dots)
    for enemy in enemies:
        scan_x = int(enemy.world_x * scale)
        # Calculate y-position based on altitude
        scan_y = SCANNER_TOP_Y + int(((enemy.world_y - 60) / PLAYABLE_HEIGHT) * SCANNER_DISPLAY_HEIGHT)
        scan_y = max(SCANNER_TOP_Y, min(SCANNER_BOTTOM_Y, scan_y)) # Clamp to scanner area
        
        color = RED
        if isinstance(enemy, Lander) and enemy.has_humanoid:
            color = PURPLE # Change color if carrying humanoid
        elif isinstance(enemy, Mutant):
            color = ORANGE # Mutants are a different color
            
        pygame.draw.circle(screen, color, (scan_x, scan_y), 2)
    
    # Humanoids (white dots) - always at the bottom
    for h in humanoids:
        color = WHITE
        if h.is_falling: color = YELLOW
        if h.is_carried: color = CYAN
        scan_x = int(h.world_x * scale)
        pygame.draw.circle(screen, color, (scan_x, 45), 1) # Fixed at bottom
    
    # Player (larger yellow dot with direction indicator)
    player_scan_x = int(player.world_x * scale)
    player_scan_y = SCANNER_TOP_Y + int(((player.world_y - 60) / PLAYABLE_HEIGHT) * SCANNER_DISPLAY_HEIGHT)
    player_scan_y = max(SCANNER_TOP_Y, min(SCANNER_BOTTOM_Y, player_scan_y)) # Clamp
    
    pygame.draw.circle(screen, YELLOW, (player_scan_x, player_scan_y), 3)
    # Direction indicator
    direction = 5 if player.facing_right else -5
    pygame.draw.line(screen, YELLOW, (player_scan_x, player_scan_y), (player_scan_x + direction, player_scan_y), 2)
    
    # View window indicator
    view_start = int(camera_x * scale)
    view_width = int(SCREEN_WIDTH * scale)
    pygame.draw.rect(screen, WHITE, (view_start, 23, view_width, 5), 1)

def draw_text(text, x, y, color=WHITE):
    text_surface = font.render(text, True, color)
    screen.blit(text_surface, (x, y))

def update_camera():
    global camera_x
    # Smooth camera following with proper viewport mechanics
    target_x = player.world_x - SCREEN_WIDTH / 2
    camera_x += (target_x - camera_x) * 0.1
    
    # Keep camera within world bounds
    camera_x = max(0, min(WORLD_WIDTH - SCREEN_WIDTH, camera_x))

# --- Game Setup ---
all_sprites = pygame.sprite.Group()
enemies = pygame.sprite.Group()
lasers = pygame.sprite.Group()
humanoids = pygame.sprite.Group()
particles = pygame.sprite.Group() # New group for particles

# Generate terrain points for more varied landscape
terrain_points = []
for x in range(0, WORLD_WIDTH + 60, 60): # Ensure it covers the whole world
    y = GROUND_LEVEL + random.randint(-25, 25)
    terrain_points.append((x, y))

player = Player()
all_sprites.add(player)

# Create humanoids
for _ in range(10):
    h = Humanoid()
    all_sprites.add(h)
    humanoids.add(h)

# Create landers
for _ in range(6):
    e = Lander()
    all_sprites.add(e)
    enemies.add(e)

camera_x = player.world_x - SCREEN_WIDTH / 2
score = 0

# --- Main Game Loop ---
running = True
game_over = False

while running:
    # --- Event Handling ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            if event.key == pygame.K_SPACE:
                player.shoot()
            if event.key == pygame.K_b and player.bombs > 0:  # Smart Bomb
                player.bombs -= 1
                for enemy in list(enemies):
                    # Only destroy enemies on screen
                    if camera_x - 50 < enemy.world_x < camera_x + SCREEN_WIDTH + 50:
                        if isinstance(enemy, Lander) and enemy.has_humanoid and enemy.target_humanoid:
                            enemy.target_humanoid.is_abducted = False
                            enemy.target_humanoid.is_falling = True
                            enemy.target_humanoid.fall_start_y = enemy.target_humanoid.world_y
                        
                        color = ORANGE if isinstance(enemy, Mutant) else GREEN
                        create_explosion(enemy.world_x, enemy.world_y, color)
                        enemy.kill()
                        score += 100
                        explosion_sound.play()

    if game_over:
        draw_text("GAME OVER - Press ESC to quit", SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT//2, RED)
        pygame.display.flip()
        continue

    # --- Update ---
    all_sprites.update()
    update_camera()
    
    # Update stars
    for star in stars:
        star.update()

    # Collision: Laser hits Lander
    hits = pygame.sprite.groupcollide(enemies, lasers, True, True)
    for hit in hits:
        score += 150
        explosion_sound.play()
        color = ORANGE if isinstance(hit, Mutant) else GREEN
        create_explosion(hit.world_x, hit.world_y, color)
        # Release humanoid if lander was carrying one
        if isinstance(hit, Lander) and hit.has_humanoid and hit.target_humanoid and hit.target_humanoid.alive():
            hit.target_humanoid.is_abducted = False
            hit.target_humanoid.is_falling = True
            hit.target_humanoid.fall_start_y = hit.target_humanoid.world_y

    # Collision: Player hits Lander
    if not player.invincible:
        hits = pygame.sprite.spritecollide(player, enemies, True)
        if hits:
            player.lives -= 1
            explosion_sound.play()
            for hit in hits: # Create explosion for each enemy hit
                color = ORANGE if isinstance(hit, Mutant) else GREEN
                create_explosion(hit.world_x, hit.world_y, color)

            if player.lives <= 0:
                game_over = True
            else:
                # No level reset, just respawn player
                player.respawn()
    
    # Player catches/releases humanoid
    if player.carried_humanoid:
        # Check for release condition
        current_ground_y = get_terrain_height_at(player.world_x)
        if player.world_y >= current_ground_y - 10:
            player.carried_humanoid.is_carried = False
            player.carried_humanoid.world_y = current_ground_y - 8
            player.carried_humanoid = None
            score += 1000 # Bonus for safe delivery
            rescue_sound.play()
    else:
        # Check for catch condition
        for h in humanoids.sprites():
            if h.is_falling:
                distance = math.hypot(player.world_x - h.world_x, player.world_y - h.world_y)
                if distance < 25:  # Close enough to catch
                    h.is_falling = False
                    h.is_carried = True
                    h.velocity_y = 0
                    player.carried_humanoid = h
                    rescue_sound.play()
                    break # Only catch one at a time

    # Spawn new enemies if too few remain
    if len(enemies) < 3:
        for _ in range(2):
            e = Lander()
            all_sprites.add(e)
            enemies.add(e)
    
    # Check if all humanoids are gone
    if len(humanoids) == 0:
        game_over = True

    # --- Drawing ---
    screen.fill(BLACK)
    
    # Draw starfield
    for star in stars:
        star.draw(screen, camera_x)

    # Update sprite screen positions based on camera
    for sprite in all_sprites:
        sprite.rect.centerx = int(sprite.world_x - camera_x)
        sprite.rect.centery = int(sprite.world_y)

    # Draw all game objects
    all_sprites.draw(screen)
    draw_terrain()
    draw_scanner()

    # Draw UI
    draw_text(f"SCORE: {score:06d}", 10, SCREEN_HEIGHT - 35)
    draw_text(f"LIVES: {player.lives}", 200, SCREEN_HEIGHT - 35)
    draw_text(f"BOMBS: {player.bombs}", 320, SCREEN_HEIGHT - 35)
    draw_text(f"HUMANS: {len(humanoids)}", 450, SCREEN_HEIGHT - 35)
    
    # Draw altitude indicator
    altitude = int((get_terrain_height_at(player.world_x) - player.world_y) / 2)
    draw_text(f"ALT: {altitude:03d}", 600, SCREEN_HEIGHT - 35)

    # --- Update Display ---
    pygame.display.flip()
    clock.tick(FPS)

# --- Quit Pygame ---
pygame.quit()
sys.exit()
